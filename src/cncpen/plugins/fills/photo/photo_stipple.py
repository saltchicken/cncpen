import argparse
import random
from typing import Any, List

import argcomplete
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill


@register_fill("photo_stipple")
class PhotoStippleFill:

    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--image",
                            default=None,
                            help="Input image for contouring"
                           ).completer = argcomplete.completers.FilesCompleter(
                               allowednames=(".png", ".jpg", ".jpeg"))

        parser.add_argument("--dots",
                            type=int,
                            default=5000,
                            help="Target number of stipple dots")

    def generate(self, shape: BaseGeometry,
                 context: 'RenderContext') -> List[LineString]:
        dots = getattr(context.args, 'dots', 5000)
        sampler = getattr(context.args, 'sampler', None)
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
