import argparse
import math
from typing import Any, List

import argcomplete
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill


@register_fill("photo_wave")
class PhotoWaveFill:
    handles_image_natively = True

    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--image",
                            default=None,
                            help="Input image for contouring"
                           ).completer = argcomplete.completers.FilesCompleter(
                               allowednames=(".png", ".jpg", ".jpeg"))

        parser.add_argument("--lines",
                            type=int,
                            default=80,
                            help="Number of horizontal wave lines")
        parser.add_argument("--amp",
                            type=float,
                            default=2.0,
                            help="Maximum wave amplitude multiplier")

    def generate(self, shape: BaseGeometry,
                 context: 'RenderContext') -> List[LineString]:
        lines = getattr(context.args, 'lines', 80)
        amp = getattr(context.args, 'amp', 2.0)
        sampler = getattr(context.args, 'sampler', None)
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
