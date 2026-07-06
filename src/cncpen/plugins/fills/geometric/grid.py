import argparse
from typing import Any, List

import argcomplete
from pydantic import BaseModel
from pydantic import Field
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill
from cncpen import RenderContext


class GridConfig(BaseModel):
    cell_size: float = Field(default=2.0, gt=0.0)


@register_fill("grid", config_class=GridConfig)
class GridFill:
    """Generates a standard orthogonal square grid tessellation."""

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        cell_size = context.config.params.cell_size
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
