import argparse
import math
import random
from typing import Any, List

import argcomplete
from pydantic import BaseModel
from pydantic import Field
from shapely.geometry import LineString

from cncpen import register_modification
from cncpen import RenderContext


class RoughenConfig(BaseModel):
    roughen_step: float = Field(default=1.0, gt=0.0)
    roughen_amp: float = Field(default=0.0, ge=0.0)


@register_modification("roughen", config_class=RoughenConfig)
class RoughenMod:

    def apply(self, lines: List[LineString],
              context: RenderContext) -> List[LineString]:
        params = context.config.params
        step = params.roughen_step
        amp = params.roughen_amp
        return [self._roughen_line(line, step, amp) for line in lines]

    def _roughen_line(self, line: LineString, segment_length: float,
                      amplitude: float) -> LineString:
        if line.length <= segment_length:
            return line

        num_segments = max(1, int(math.ceil(line.length / segment_length)))
        points = [
            line.interpolate(i / num_segments, normalized=True).coords[0]
            for i in range(num_segments + 1)
        ]

        if len(points) < 3:
            return line

        wiggled_coords = [points[0]]
        for i in range(1, len(points) - 1):
            px, py = points[i - 1]
            nx, ny = points[i + 1]
            dx, dy = nx - px, ny - py
            length = math.hypot(dx, dy)

            if length == 0:
                wiggled_coords.append(points[i])
                continue

            norm_x, norm_y = -dy / length, dx / length
            displacement = random.gauss(0, amplitude)
            wiggled_coords.append((points[i][0] + norm_x * displacement,
                                   points[i][1] + norm_y * displacement))

        wiggled_coords.append(points[-1])
        return LineString(wiggled_coords)
