import argparse
import math
from typing import Any, List

import argcomplete
from pydantic import BaseModel
from pydantic import Field
from shapely.geometry import LineString

from cncpen import register_modification
from cncpen import RenderContext


class FisheyeConfig(BaseModel):
    fisheye: float = Field(default=0.0)


@register_modification("fisheye", config_class=FisheyeConfig)
class FisheyeMod:

    def apply(self, lines: List[LineString],
              context: RenderContext) -> List[LineString]:
        fisheye = context.config.params.fisheye
        if not fisheye or context.max_r <= 0:
            return lines

        distorted_lines = []
        for line in lines:
            length = line.length
            if length == 0:
                continue

            num_segments = max(2, int(math.ceil(length / 0.5)))
            points = [
                line.interpolate(i / num_segments, normalized=True).coords[0]
                for i in range(num_segments + 1)
            ]

            warped_coords = []
            for px, py in points:
                dx, dy = px - context.centroid.x, py - context.centroid.y
                r = math.hypot(dx, dy)
                f = 1.0 + fisheye * ((r / context.max_r)**2) if r > 0 else 1.0
                warped_coords.append(
                    (context.centroid.x + dx * f, context.centroid.y + dy * f))

            distorted_lines.append(LineString(warped_coords))

        return distorted_lines
