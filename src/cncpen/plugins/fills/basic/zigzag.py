from typing import List

from pydantic import BaseModel
from pydantic import Field
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_operation
from cncpen import RenderContext


class ZigZagConfig(BaseModel):
    spacing: float = Field(default=2.0, gt=0.0)


@register_operation("zigzag", config_class=ZigZagConfig)
class ZigZagFill:

    def process(self, lines: List[LineString], shape: BaseGeometry, context: RenderContext) -> List[LineString]:
        minx, miny, maxx, maxy = shape.bounds
        spacing = context.config.params.spacing
        offset = ((maxy - miny) % spacing) / 2.0
        y = miny + offset + (spacing / 2.0)
        out_lines = []
        left_to_right = True

        while y <= maxy:
            x_start, x_end = (minx - 1,
                              maxx + 1) if left_to_right else (maxx + 1,
                                                               minx - 1)
            out_lines.append(LineString([(x_start, y), (x_end, y)]))
            y += spacing
            left_to_right = not left_to_right

        return lines + out_lines
