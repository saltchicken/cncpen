import math
from typing import List

from pydantic import BaseModel
from pydantic import Field
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill
from cncpen import RenderContext


class GuillocheConfig(BaseModel):
    major_radius: float = Field(default=50.0)
    minor_radius: float = Field(default=-15.0)
    pen_offset: float = Field(default=25.0)
    revolutions: int = Field(default=10, gt=0)
    resolution: float = Field(default=0.05, gt=0.0)


@register_fill("guilloche", config_class=GuillocheConfig)
class GuillocheFill:

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        params = context.config.params

        R = params.major_radius
        r = params.minor_radius
        p = params.pen_offset
        revolutions = params.revolutions
        resolution = params.resolution

        # Center the pattern on the bounding geometry's centroid
        cx, cy = context.centroid.x, context.centroid.y

        points = []
        max_theta = revolutions * 2 * math.pi
        theta = 0.0

        # Pre-calculate the ratio to save operations in the loop
        if r == 0:
            r = 0.0001  # Prevent division by zero
        ratio = (R + r) / r

        while theta <= max_theta:
            # Parametric equations for the roulette curve
            x = cx + (R + r) * math.cos(theta) + p * math.cos(ratio * theta)
            y = cy + (R + r) * math.sin(theta) + p * math.sin(ratio * theta)

            points.append((x, y))
            theta += resolution

        # Ensure the loop closes cleanly if it completes a perfect cycle
        if points:
            points.append((cx + (R + r) * math.cos(max_theta) +
                           p * math.cos(ratio * max_theta),
                           cy + (R + r) * math.sin(max_theta) +
                           p * math.sin(ratio * max_theta)))

        if len(points) > 1:
            return [LineString(points)]
        return []
