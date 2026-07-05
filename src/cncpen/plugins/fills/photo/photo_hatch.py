import argparse
from typing import Any, List

import argcomplete
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill
from cncpen import ImageSampler

@register_fill("photo_hatch")
class PhotoHatchFill:

    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--image",
                            default=None,
                            help="Input image for contouring"
                           ).completer = argcomplete.completers.FilesCompleter(
                               allowednames=(".png", ".jpg", ".jpeg"))

        parser.add_argument("--cell-size",
                            type=float,
                            default=2.0,
                            help="Size of the hatching grid cells")

    def generate(self, shape: BaseGeometry,
                 context: 'RenderContext') -> List[LineString]:
        cell_size = getattr(context.args, 'cell_size', 2.0)
        image_path = getattr(context.args, 'image', None)
        
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
