import argparse
import random
from typing import Any, List

import argcomplete
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import ImageSampler
from cncpen import register_fill
from cncpen import RenderContext


@register_fill("photo_stipple")
class PhotoStippleFill:

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        dots = context.config.params.get('dots', 5000)
        sampler = context.config.params.get('sampler', None)
        image_path = context.config.params.get('image', None)

        if not sampler and image_path:
            sampler = ImageSampler(image_path, context.bounds)

        if not sampler:
            return []

        minx, miny, maxx, maxy = shape.bounds
        width, height = maxx - minx, maxy - miny

        output_paths = []
        attempts = 0
        max_attempts = dots * 10

        while len(output_paths) < dots and attempts < max_attempts:
            attempts += 1

            rx = random.uniform(0, width)
            ry = random.uniform(0, height)
            actual_x = minx + rx
            actual_y = miny + ry

            darkness = sampler.get_darkness(actual_x, actual_y)

            if random.random() < darkness:
                output_paths.append(
                    LineString([(actual_x, actual_y),
                                (actual_x + 0.1, actual_y)]))

        return output_paths
