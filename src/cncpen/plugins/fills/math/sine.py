import argparse
import math
from typing import Any, List

import argcomplete
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill


@register_fill("sine")
class SineFill:
    """Generates back-and-forth sine wave fill paths, optionally modulated by an image."""

    def generate(self, shape: BaseGeometry,
                 context: 'RenderContext') -> List[LineString]:
        spacing = context.config.get('spacing', 2.0)
        amplitude = context.config.get('amplitude', 1.0)
        wavelength = context.config.get('wavelength', 5.0)
        sampler = context.config.get('sampler', None)

        minx, miny, maxx, maxy = shape.bounds
        y = miny + spacing
        lines = []
        left_to_right = True
        resolution = 0.2

        while y <= maxy + amplitude:
            x_start, x_end = minx - 1, maxx + 1
            wave_points = []
            num_steps = int(math.ceil((x_end - x_start) / resolution))

            for i in range(num_steps + 1):
                cx = x_start + i * resolution

                # Default factor is 1.0 if no image sampler is present
                mod_factor = sampler.get_darkness(cx, y) if sampler else 1.0

                # Apply the modulation directly to the amplitude mapping
                current_amp = amplitude * mod_factor
                cy = y + current_amp * math.sin(2 * math.pi * cx / wavelength)
                wave_points.append((cx, cy))

            if not left_to_right:
                wave_points.reverse()

            lines.append(LineString(wave_points))
            y += spacing
            left_to_right = not left_to_right

        return lines
