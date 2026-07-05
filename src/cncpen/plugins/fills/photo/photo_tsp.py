import argparse
import math
import random
from typing import Any, List

import argcomplete
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill


@register_fill("photo_tsp")
class PhotoTSPFill:
    handles_image_natively = True

    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--image",
                            default=None,
                            help="Input image for contouring"
                           ).completer = argcomplete.completers.FilesCompleter(
                               allowednames=(".png", ".jpg", ".jpeg"))

        parser.add_argument("--nodes",
                            type=int,
                            default=2000,
                            help="Number of nodes to connect")

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        nodes = getattr(context.args, 'nodes', 2000)
        sampler = getattr(context.args, 'sampler', None)
        if not sampler:
            return []

        minx, miny, maxx, maxy = shape.bounds
        width, height = maxx - minx, maxy - miny

        # 1. Generate weighted random points using the sampler
        points = []
        attempts = 0
        while len(points) < nodes and attempts < (nodes * 10):
            attempts += 1
            rx, ry = random.uniform(0, width), random.uniform(0, height)
            actual_x, actual_y = minx + rx, miny + ry

            if random.random() < sampler.get_darkness(actual_x, actual_y):
                points.append((actual_x, actual_y))

        if not points:
            return []

        # 2. Greedy Nearest Neighbor TSP
        current = points.pop(0)
        route = [current]

        while points:
            best_idx = -1
            best_dist = float('inf')

            for i, p in enumerate(points):
                dist = math.hypot(current[0] - p[0], current[1] - p[1])
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i

            current = points.pop(best_idx)
            route.append(current)

        return [LineString(route)]
