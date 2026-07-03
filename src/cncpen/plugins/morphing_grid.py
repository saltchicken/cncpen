import argparse
import math
from typing import List, Any

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen.fills import register_fill


@register_fill("morphing_grid")
class MorphingGridFill:
    """
    Generates a grid of geometric shapes that morph in complexity,
    scale, and rotation across the geometry to simulate a waveform progression.
    """
    
    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--cell-size", type=float, default=5.0,
                            help="Size of the bounding grid for each morphing cell (default: 5.0)")
        parser.add_argument("--morph-cycles", type=float, default=1.0,
                            help="Number of complete waveform morph cycles across the shape (default: 1.0)")

    def generate(self, shape: BaseGeometry, spacing: float, cell_size: float = 5.0, 
                 morph_cycles: float = 1.0, **kwargs: Any) -> List[LineString]:
        
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
