import argparse
from typing import Any, List

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen.fills import register_fill


@register_fill("grid")
class GridFill:
    """Generates a standard orthogonal square grid tessellation."""

    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--cell-size",
                            type=float,
                            default=2.0,
                            help="Size of the grid squares (default: 2.0)")

    def generate(self,
                 shape: BaseGeometry,
                 cell_size: float = 2.0,
                 **kwargs: Any) -> List[LineString]:
        minx, miny, maxx, maxy = shape.bounds

        if cell_size <= 0:
            return []

        lines = []

        # Vertical grid lines
        x = minx
        while x <= maxx:
            lines.append(LineString([(x, miny), (x, maxy)]))
            x += cell_size

        # Horizontal grid lines
        y = miny
        while y <= maxy:
            lines.append(LineString([(minx, y), (maxx, y)]))
            y += cell_size

        return lines
