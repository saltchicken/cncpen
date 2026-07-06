import argparse
import math
from typing import Any, List

import argcomplete
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill
from cncpen import RenderContext


@register_fill("spiral")
class SpiralFill:
    """Generates an Archimedean spiral outward from the shape's centroid."""

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        spacing = context.config.params.get('spacing', 2.0)
        resolution = context.config.params.get('resolution', 0.5)

        # Fallback to prevent infinite loops if invalid arguments are passed
        if spacing <= 0.01:
            spacing = 1.0

        # 1. Determine the bounding box and center point
        minx, miny, maxx, maxy = shape.bounds
        cx = (minx + maxx) / 2.0
        cy = (miny + maxy) / 2.0

        # 2. Calculate the maximum radius needed to cover the furthest corner
        corners = [(minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy)]
        max_r = max(math.hypot(x - cx, y - cy) for x, y in corners)

        if max_r == 0:
            return []

        # 3. Setup spiral parameters
        b = spacing / (2.0 * math.pi)
        max_theta = max_r / b

        points = []
        theta = 0.0

        # 4. Generate points along the spiral
        while theta <= max_theta:
            r = b * theta
            x = cx + r * math.cos(theta)
            y = cy + r * math.sin(theta)
            points.append((x, y))

            # Dynamically calculate the angular step based on the target resolution
            # As the radius gets larger, the angle step must get smaller to maintain arc length
            if r > resolution:
                step = resolution / r
            else:
                step = resolution  # Avoid dividing by near-zero at the origin

            # Clamp the step to prevent overly massive jumps near the center
            step = min(max(step, 0.01), math.pi / 4)
            theta += step

        # A LineString requires at least 2 points
        if len(points) < 2:
            return []

        return [LineString(points)]
