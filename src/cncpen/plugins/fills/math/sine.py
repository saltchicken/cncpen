import argparse
import argcomplete
import math
from typing import Any, List

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill


@register_fill("sine")
class SineFill:
    """Generates back-and-forth sine wave fill paths, optionally modulated by an image."""

    handles_image_natively = True

    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--amplitude",
            type=float,
            default=1.0,
            help="Base amplitude for the sine wave pattern (default: 1.0)")
        parser.add_argument(
            "--wavelength",
            type=float,
            default=5.0,
            help="Wavelength for the sine wave pattern (default: 5.0)")

    def generate(self,
                 shape: BaseGeometry,
                 spacing: float,
                 amplitude: float = 1.0,
                 wavelength: float = 5.0,
                 sampler=None,
                 **kwargs: Any) -> List[LineString]:

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
