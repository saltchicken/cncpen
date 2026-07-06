import argparse
from typing import Any, List

import argcomplete
import numpy as np
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry
from skimage import measure

from cncpen import ImageSampler
from cncpen import register_fill
from cncpen import RenderContext


@register_fill("photo-contour")
class PhotoContourFill:
    """Generates topographic contours driven by image darkness."""

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        sampler = context.config.params.get('sampler', None)
        levels = context.config.params.get('levels', 15)
        resolution = context.config.params.get('resolution', 0.5)
        min_length = context.config.params.get('min_length', 2.0)
        image_path = context.config.params.get('image', None)

        if not sampler and image_path:
            sampler = ImageSampler(image_path, context.bounds)

        if not sampler:
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
                    if line.length >= min_length:
                        lines.append(line)

        return lines
