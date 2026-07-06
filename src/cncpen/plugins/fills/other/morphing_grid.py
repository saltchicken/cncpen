import argparse
import math
from typing import Any, List

import argcomplete
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill


@register_fill("morphing_grid")
class MorphingGridFill:
    """
    Generates a grid of geometric shapes. Morphs in complexity, scale, and rotation 
    based EITHER on an underlying photo sampler OR a mathematical waveform progression.
    """

    def generate(self, shape: BaseGeometry,
                 context: 'RenderContext') -> List[LineString]:
        spacing = context.config.get('spacing', 2.0)
        cell_size = context.config.get('cell_size', 5.0)
        morph_cycles = context.config.get('morph_cycles', 1.0)
        sampler = context.config.get('sampler', None)

        minx, miny, maxx, maxy = shape.bounds
        width = maxx - minx
        height = maxy - miny

        if width == 0 or height == 0:
            return []

        step = max(spacing, cell_size)
        lines = []

        y = miny + (step / 2)
        while y <= maxy:
            x = minx + (step / 2)
            while x <= maxx:

                if sampler:
                    # Photo-Driven Mode
                    norm_phase = sampler.get_darkness(x, y)
                else:
                    # Math-Driven Mode
                    nx = (x - minx) / width
                    ny = (y - miny) / height
                    t = nx * math.cos(math.pi / 4) + ny * math.sin(math.pi / 4)
                    phase = math.sin(t * math.pi * 2 * morph_cycles)
                    norm_phase = (phase + 1) / 2.0

                sides = int(3 + (5 * norm_phase))
                radius = (step / 2.0) * (0.3 + (0.6 * norm_phase))
                rotation_rads = norm_phase * math.pi

                coords = []
                for i in range(sides + 1):
                    theta = (i * 2 * math.pi / sides) + rotation_rads
                    px = x + radius * math.cos(theta)
                    py = y + radius * math.sin(theta)
                    coords.append((px, py))

                lines.append(LineString(coords))
                x += step
            y += step

        return lines
