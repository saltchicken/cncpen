from typing import List

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill, RenderContext


@register_fill("zigzag")
class ZigZagFill:

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        minx, miny, maxx, maxy = shape.bounds
        spacing = context.config.params.get('spacing', 2.0)
        offset = ((maxy - miny) % spacing) / 2.0
        y = miny + offset + (spacing / 2.0)
        lines = []
        left_to_right = True

        while y <= maxy:
            x_start, x_end = (minx - 1, maxx + 1) if left_to_right else (maxx + 1, minx - 1)
            lines.append(LineString([(x_start, y), (x_end, y)]))
            y += spacing
            left_to_right = not left_to_right

        return lines
