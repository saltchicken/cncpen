import argparse
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


class PhotoStippleConfig(BaseModel):
    dots: int = Field(default=5000, gt=0)
    image: str | None = None
    sampler: Any = None


@register_fill("photo_stipple", config_class=PhotoStippleConfig)
class PhotoStippleFill:

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        params = context.config.params
        dots = params.dots
        sampler = params.sampler
        image_path = params.image

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
