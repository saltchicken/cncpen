import argparse
import math
from typing import Any, List

import argcomplete
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill


@register_fill("triangle")
class TriangleFill:
    """Generates an equilateral triangular (isometric grid) tessellation."""

    def generate(self, shape: BaseGeometry,
                 context: 'RenderContext') -> List[LineString]:
        cell_size = context.config.get('cell_size', 5.0)
        minx, miny, maxx, maxy = shape.bounds
        cx, cy = shape.centroid.x, shape.centroid.y

        # Calculate a bounding radius large enough to cover the shape when rotated
        diag = math.hypot(maxx - minx, maxy - miny)
        r = diag / 2.0 + cell_size

        # Perpendicular distance between triangle grid lines
        spacing = cell_size * math.sqrt(3.0) / 2.0
        if spacing <= 0:
            return []

        lines = []

        # Generate parallel bounding lines at 0, 60, and 120 degrees
        for angle_deg in [0, 60, 120]:
            angle_rad = math.radians(angle_deg)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)

            # Normal vector to calculate parallel offsets
            nx = -sin_a
            ny = cos_a

            num_lines = int(math.ceil(2 * r / spacing))
            for i in range(-num_lines // 2, num_lines // 2 + 1):
                offset = i * spacing
                px = cx + nx * offset
                py = cy + ny * offset

                start_x = px - cos_a * r
                start_y = py - sin_a * r
                end_x = px + cos_a * r
                end_y = py + sin_a * r

                lines.append(LineString([(start_x, start_y), (end_x, end_y)]))

        return lines
