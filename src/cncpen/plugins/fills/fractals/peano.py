import argparse
import math
from typing import Any, List

import argcomplete
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from pydantic import BaseModel, Field

from cncpen import register_fill
from cncpen import RenderContext


class PeanoConfig(BaseModel):
    spacing: float = Field(default=2.0, gt=0.0)


@register_fill("peano", config_class=PeanoConfig)
class PeanoFill:
    """Generates a mathematically exact, continuous base-3 Peano space-filling curve."""

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        spacing = context.config.params.spacing
        minx, miny, maxx, maxy = shape.bounds
        width = maxx - minx
        height = maxy - miny
        size = max(width, height)
        safe_spacing = max(spacing, 0.1)

        # Calculate required recursion depth
        if size > safe_spacing:
            order = int(math.ceil(math.log(size / safe_spacing, 3)))
        else:
            order = 1

        # Cap order at 5 (59,049 points) to prevent massive memory/CPU usage
        order = min(max(order, 1), 5)

        num_points = 9**order
        pts = []

        cells_per_axis = 3**order
        cell_size = size / cells_per_axis

        for i in range(num_points):
            # 1. Extract base-3 digits (2 digits per order level)
            temp = i
            digits = []
            for _ in range(2 * order):
                digits.append(temp % 3)
                temp //= 3
            digits.reverse()

            x_grid, y_grid = 0, 0
            sum_t_even = 0
            sum_t_odd = 0

            # 2. Compute exact grid coordinates using parity rules
            for k in range(1, order + 1):
                t_odd = digits[2 * k - 2]
                t_even = digits[2 * k - 1]

                # Compute x_k (inverts if sum of previous evens is odd)
                if sum_t_even % 2 == 0:
                    x_k = t_odd
                else:
                    x_k = 2 - t_odd

                sum_t_odd += t_odd

                # Compute y_k (inverts if sum of previous odds is odd)
                if sum_t_odd % 2 == 0:
                    y_k = t_even
                else:
                    y_k = 2 - t_even

                sum_t_even += t_even

                # Accumulate the coordinate values
                x_grid = x_grid * 3 + x_k
                y_grid = y_grid * 3 + y_k

            # 3. Map to physical coordinates (centered in the cell)
            px = minx + (x_grid + 0.5) * cell_size
            py = miny + (y_grid + 0.5) * cell_size
            pts.append((px, py))

        if len(pts) < 2:
            return []

        return [LineString(pts)]
