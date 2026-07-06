import argparse
import math
import random
from typing import Any, List

import argcomplete
from pydantic import BaseModel
from pydantic import Field
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import ImageSampler
from cncpen import register_fill
from cncpen import RenderContext


class PhotoTSPConfig(BaseModel):
    nodes: int = Field(default=2000, gt=1)
    image: str | None = None
    sampler: Any = None


@register_fill("photo_tsp", config_class=PhotoTSPConfig)
class PhotoTSPFill:

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        params = context.config.params
        nodes = params.nodes
        sampler = params.sampler
        image_path = params.image

        if not sampler and image_path:
            sampler = ImageSampler(image_path, context.bounds)

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
