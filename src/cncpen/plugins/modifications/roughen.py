import argparse
import argcomplete
import math
import random
from typing import Any, List
from shapely.geometry import LineString
from cncpen import register_modification

@register_modification("roughen")
class RoughenMod:
    @classmethod
    def setup_cli(cls, group: argparse._ArgumentGroup) -> None:
        group.add_argument("--roughen-amp",
                           type=float,
                           default=0.0,
                           help="Amplitude of hand-drawn noise")
        group.add_argument("--roughen-step",
                           type=float,
                           default=1.0,
                           help="Resolution of hand-drawn noise")

    def is_active(self, args: argparse.Namespace) -> bool:
        return getattr(args, 'roughen_amp', 0.0) > 0.0

    def apply(self, lines: List[LineString], args: argparse.Namespace,
              **kwargs: Any) -> List[LineString]:
        return [
            self._roughen_line(line, args.roughen_step, args.roughen_amp)
            for line in lines
        ]

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
