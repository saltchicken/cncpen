import math
import random
from typing import List

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill
from cncpen import RenderContext


@register_fill("flow_field")
class FlowFieldFill:
    """
    Generates organic, sweeping curves by dropping 'seeds' and tracing 
    their paths through a mathematical vector field.
    """

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        # Configuration with safe defaults
        spacing = context.config.get('spacing', 3.0)
        step_length = context.config.get('step_length', 1.0)
        max_steps = context.config.get('max_steps', 50)
        scale = context.config.get('scale', 0.1)
        seed = context.config.get('seed', 42)

        random.seed(seed)
        minx, miny, maxx, maxy = shape.bounds
        width = maxx - minx
        height = maxy - miny

        if width <= 0 or height <= 0:
            return []

        # 1. Distribute starting seeds across the bounding box
        seeds = []
        x = minx
        while x <= maxx:
            y = miny
            while y <= maxy:
                # Add a little jitter to the grid to prevent artificial symmetry
                jx = x + random.uniform(-spacing / 2, spacing / 2)
                jy = y + random.uniform(-spacing / 2, spacing / 2)
                seeds.append((jx, jy))
                y += spacing
            x += spacing

        # 2. Define the mathematical flow
        cx, cy = shape.centroid.x, shape.centroid.y

        def get_field_angle(px: float, py: float) -> float:
            """Calculates a pseudo-random angle based on position."""
            nx = (px - cx) * scale
            ny = (py - cy) * scale
            # This combination of trig functions creates asymmetric, non-repeating swirls
            angle = math.sin(nx) + math.cos(ny) + math.sin(nx * ny * 0.5)
            return angle * math.pi

        # 3. Trace the paths through the field
        lines = []
        for sx, sy in seeds:
            path = [(sx, sy)]
            cx_pt, cy_pt = sx, sy

            for _ in range(max_steps):
                theta = get_field_angle(cx_pt, cy_pt)
                nx_pt = cx_pt + step_length * math.cos(theta)
                ny_pt = cy_pt + step_length * math.sin(theta)

                path.append((nx_pt, ny_pt))
                cx_pt, cy_pt = nx_pt, ny_pt

                # Terminate early if the line wanders way outside the draw area
                if not (minx - 10 <= cx_pt <= maxx + 10 and
                        miny - 10 <= cy_pt <= maxy + 10):
                    break

            if len(path) > 1:
                lines.append(LineString(path))

        # Note: We don't need to clip these lines to the polygon shape here;
        # the main cncpen pipeline handles boundary clipping automatically.
        return lines
