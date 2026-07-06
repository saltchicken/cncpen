import argparse
from typing import Any, List

import argcomplete
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import ImageSampler
from cncpen import register_fill
from cncpen import RenderContext


@register_fill("photo_hatch")
class PhotoHatchFill:

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        cell_size = context.config.params.get('cell_size', 2.0)
        image_path = context.config.params.get('image', None)

        # 2. Check for the image path directly
        if not image_path:
            print("Warning: --image argument is required for photo_hatch.")
            return []

        # 3. Initialize the sampler using the global context bounds
        sampler = ImageSampler(image_path, context.bounds)

        minx, miny, maxx, maxy = shape.bounds
        output_paths = []

        x = minx
        while x < maxx:
            y = miny
            while y < maxy:
                cx, cy = x + (cell_size / 2), y + (cell_size / 2)
                darkness = sampler.get_darkness(cx, cy)

                if darkness > 0.3:
                    output_paths.append(
                        LineString([(x, y), (x + cell_size, y + cell_size)]))
                if darkness > 0.7:
                    output_paths.append(
                        LineString([(x, y + cell_size), (x + cell_size, y)]))

                y += cell_size
            x += cell_size

        return output_paths
