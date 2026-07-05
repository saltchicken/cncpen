import argparse
from typing import Any, List

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill


@register_fill("photo_hatch")
class PhotoHatchFill:
    handles_image_natively = True

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

    def generate(self,
                 shape: BaseGeometry,
                 cell_size: float = 2.0,
                 sampler=None,
                 **kwargs: Any) -> List[LineString]:
        if not sampler:
            return []

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
