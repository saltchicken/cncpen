import argparse
import math
from typing import Any, List
from shapely.geometry import LineString
from cncpen import register_modification

@register_modification("fisheye")
class FisheyeMod:
    @classmethod
    def setup_cli(cls, group: argparse._ArgumentGroup) -> None:
        group.add_argument("--fisheye",
                           type=float,
                           default=0.0,
                           help="Apply radial distortion")

    def is_active(self, args: argparse.Namespace) -> bool:
        return getattr(args, 'fisheye', 0.0) != 0.0

    def apply(self,
              lines: List[LineString],
              args: argparse.Namespace,
              centroid: Any = None,
              max_r: float = 0.0,
              **kwargs: Any) -> List[LineString]:
        if not centroid or max_r <= 0:
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
                dx, dy = px - centroid.x, py - centroid.y
                r = math.hypot(dx, dy)
                f = 1.0 + args.fisheye * ((r / max_r)**2) if r > 0 else 1.0
                warped_coords.append((centroid.x + dx * f, centroid.y + dy * f))

            distorted_lines.append(LineString(warped_coords))

        return distorted_lines
