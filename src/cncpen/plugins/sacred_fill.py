import argparse
import math
from typing import List, Any

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from cncpen.fills import _apply_pattern_to_shape
from cncpen.fills import register_fill


@register_fill("sacred")
class SacredFill:
    """Generates a Flower of Life (overlapping circles) sacred geometry fill."""
    
    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        pass

    def generate(self, shape: BaseGeometry, spacing: float, angle: float = 0.0, **kwargs: Any) -> List[List[tuple[float, float]]]:
        def sacred_generator(p, spacing):
            minx, miny, maxx, maxy = p.bounds
            radius = max(spacing, 0.1)
            dx = radius
            dy = radius * math.sqrt(3) / 2.0

            # Pad the bounding box
            minx -= radius
            maxx += radius
            miny -= radius
            maxy += radius

            circles = []
            row = 0
            y = miny

            while y <= maxy:
                x_offset = (radius / 2.0) if (row % 2 != 0) else 0.0
                x = minx + x_offset
                while x <= maxx:
                    circle_outline = Point(x, y).buffer(radius, resolution=32).exterior
                    circles.append(circle_outline)
                    x += dx
                y += dy
                row += 1

            return circles

        return _apply_pattern_to_shape(shape, angle, sacred_generator, spacing=spacing)
