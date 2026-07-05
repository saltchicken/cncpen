import argparse
import math
from typing import Any, List

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen.fills import register_fill


@register_fill("zigzag")
class ZigZagFill:
    """Generates simple back-and-forth hatch paths."""

    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        pass  # Global arguments handle everything needed here

    def generate(self, shape: BaseGeometry, spacing: float,
                 **kwargs: Any) -> List[LineString]:
        minx, miny, maxx, maxy = shape.bounds
        y = miny + spacing
        lines = []
        left_to_right = True

        while y <= maxy:
            x_start, x_end = (minx - 1,
                              maxx + 1) if left_to_right else (maxx + 1,
                                                               minx - 1)
            lines.append(LineString([(x_start, y), (x_end, y)]))
            y += spacing
            left_to_right = not left_to_right

        return lines
