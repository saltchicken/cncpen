import argparse
from typing import Any, List

import numpy as np
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry
from skimage import measure

from cncpen.fills import ImageSampler
from cncpen.fills import register_fill


@register_fill("photo-contour")
class PhotoContourFill:
    """Generates topographic contours driven by image darkness."""

    # Prevents the central pipeline from dashing the lines based on darkness
    handles_image_natively = True

    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--levels",
            type=int,
            default=1,
            help=
            "Number of contour levels to extract from the image (default: 15)")
        parser.add_argument(
            "--resolution",
            type=float,
            default=0.5,
            help=
            "Sampling resolution in physical units. Lower is more detailed but slower. (default: 0.5)"
        )
        parser.add_argument(
            "--min-length",
            type=float,
            default=2.0,
            help=
            "Minimum path length to draw, filtering out pixel noise dots (default: 2.0)"
        )

    def generate(self,
                 shape: BaseGeometry,
                 sampler: ImageSampler = None,
                 levels: int = 1,
                 resolution: float = 0.5,
                 min_length: float = 2.0,
                 **kwargs: Any) -> List[LineString]:
        if not sampler:
            print(
                "Warning: 'photo-contour' requires an --image argument. Returning empty fill."
            )
            return []

        minx, miny, maxx, maxy = shape.bounds
        width = maxx - minx
        height = maxy - miny

        res_x = max(2, int(width / resolution))
        res_y = max(2, int(height / resolution))

        grid = np.zeros((res_y, res_x))
        for i in range(res_y):
            py = miny + (i / (res_y - 1)) * height
            for j in range(res_x):
                px = minx + (j / (res_x - 1)) * width
                grid[i, j] = sampler.get_darkness(px, py)

        lines = []

        thresholds = np.linspace(0.05, 0.95, levels)

        for level in thresholds:
            contours = measure.find_contours(grid, level)

            for contour in contours:
                coords = []
                for pt in contour:
                    y_idx, x_idx = pt[0], pt[1]
                    px = minx + (x_idx / (res_x - 1)) * width
                    py = miny + (y_idx / (res_y - 1)) * height
                    coords.append((px, py))

                if len(coords) >= 2:
                    line = LineString(coords)

                    # FILTER: Ignore paths that are too short (pixel noise)
                    if line.length >= min_length:
                        lines.append(line)

        return lines
