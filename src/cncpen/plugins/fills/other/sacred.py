import argparse
import math
from typing import Any, List

import argcomplete
from pydantic import BaseModel
from pydantic import Field
from shapely.geometry import LineString
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill
from cncpen import RenderContext


class SacredConfig(BaseModel):
    spacing: float = Field(default=2.0, gt=0.0)
    type: str = Field(default="seed_of_life")


@register_fill("sacred", config_class=SacredConfig)
class SacredFill:
    """Generates a Flower of Life (overlapping circles) sacred geometry fill."""

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        radius = max(context.config.params.spacing, 0.1)
        minx, miny, maxx, maxy = shape.bounds
        dx = radius
        dy = radius * math.sqrt(3) / 2.0

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
                circle_outline = Point(x, y).buffer(radius,
                                                    resolution=32).exterior
                circles.append(LineString(circle_outline.coords))
                x += dx
            y += dy
            row += 1

        return circles
