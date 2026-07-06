import argparse
import math
from typing import Any, List

import argcomplete
from pydantic import BaseModel
from pydantic import Field
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import ImageSampler
from cncpen import register_fill
from cncpen import RenderContext


class PhotoWaveConfig(BaseModel):
    lines: int = Field(default=80, gt=0)
    amp: float = Field(default=2.0)
    image: str | None = None
    sampler: Any = None


@register_fill("photo_wave", config_class=PhotoWaveConfig)
class PhotoWaveFill:

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        params = context.config.params
        lines = params.lines
        amp = params.amp
        sampler = params.sampler
        image_path = params.image

        if not sampler and image_path:
            sampler = ImageSampler(image_path, context.bounds)

        if not sampler:
            return []

        minx, miny, maxx, maxy = shape.bounds
        width, height = maxx - minx, maxy - miny
        row_spacing = height / lines
        output_paths = []

        for r in range(lines):
            y_base = miny + (r * row_spacing)
            coords = []
            steps = int(width * 5)

            for s in range(steps):
                x = minx + (s * (width / steps))

                darkness = sampler.get_darkness(x, y_base)

                y_offset = math.sin(
                    x * 3.0) * (row_spacing * amp * 0.5) * darkness
                coords.append((x, y_base + y_offset))

            output_paths.append(LineString(coords))

        return output_paths
