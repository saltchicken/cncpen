import argparse
import math
from typing import Any, List

import argcomplete
from pydantic import BaseModel
from pydantic import Field
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_operation
from cncpen import RenderContext


class HilbertConfig(BaseModel):
    spacing: float = Field(default=2.0, gt=0.0)


@register_operation("hilbert", config_class=HilbertConfig)
class HilbertFill:
    """Generates a highly intricate Hilbert space-filling curve."""

    def process(self, lines: List[LineString], shape: BaseGeometry, context: RenderContext) -> List[LineString]:
        spacing = context.config.params.spacing
        minx, miny, maxx, maxy = shape.bounds
        width = maxx - minx
        height = maxy - miny
        size = max(width, height)
        safe_spacing = max(spacing, 0.1)

        if size > safe_spacing:
            order = int(math.ceil(math.log2(size / safe_spacing)))
        else:
            order = 1
        order = min(order, 8)

        def hilbert(x0, y0, xi, xj, yi, yj, n):
            if n == 0:
                return [(x0 + (xi + yi) / 2.0, y0 + (xj + yj) / 2.0)]

            return (hilbert(x0, y0, yi / 2, yj / 2, xi / 2, xj / 2, n - 1) +
                    hilbert(x0 + xi / 2, y0 + xj / 2, xi / 2, xj / 2, yi / 2,
                            yj / 2, n - 1) +
                    hilbert(x0 + xi / 2 + yi / 2, y0 + xj / 2 + yj / 2, xi / 2,
                            xj / 2, yi / 2, yj / 2, n - 1) +
                    hilbert(x0 + xi / 2 + yi, y0 + xj / 2 + yj, -yi / 2,
                            -yj / 2, -xi / 2, -xj / 2, n - 1))

        pts = hilbert(minx, miny, size, 0.0, 0.0, size, order)
        if len(pts) < 2:
            return lines

        return lines + [LineString(pts)]
