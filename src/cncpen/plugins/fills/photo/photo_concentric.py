import argparse
from typing import Any, List

import numpy as np
from scipy import ndimage
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry
from skimage import measure

from cncpen.fills import ImageSampler
from cncpen.fills import register_fill


@register_fill("photo-concentric")
class PhotoConcentricFill:
    """Generates geometric concentric fills driven by image boundaries."""

    # Prevents the central pipeline from dashing the lines based on darkness
    handles_image_natively = True

    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--resolution",
            type=float,
            default=0.25,
            help=
            "Sampling resolution in mm. Lower is more precise but slower. (default: 0.25)"
        )
        # Note: --spacing and --threshold are already provided by your global CLI

    def generate(self,
                 shape: BaseGeometry,
                 sampler: ImageSampler = None,
                 spacing: float = 1.0,
                 threshold: float = 0.5,
                 resolution: float = 0.25,
                 **kwargs: Any) -> List[LineString]:
        if not sampler:
            print(
                "Warning: 'photo-concentric' requires an --image argument. Returning empty fill."
            )
            return []

        minx, miny, maxx, maxy = shape.bounds
        width = maxx - minx
        height = maxy - miny

        # Define grid size based on the bounding box and requested resolution
        res_x = max(2, int(width / resolution))
        res_y = max(2, int(height / resolution))

        # Sample the image darkness into a 2D NumPy array
        grid = np.zeros((res_y, res_x))
        for i in range(res_y):
            py = miny + (i / (res_y - 1)) * height
            for j in range(res_x):
                px = minx + (j / (res_x - 1)) * width
                grid[i, j] = sampler.get_darkness(px, py)

        # 1. Create a binary mask (True where the image is darker than the threshold)
        binary_mask = grid > threshold

        # 2. Calculate Euclidean Distance Transform
        # This gives every 'inside' pixel a value equal to its distance to the nearest edge (in pixels)
        distance_field = ndimage.distance_transform_edt(binary_mask)

        # 3. Convert physical spacing to pixel spacing for the contour extraction
        pixel_spacing = spacing / resolution
        max_dist = np.max(distance_field)

        lines = []

        # 4. Generate contours stepping inward by the spacing amount
        current_dist = pixel_spacing
        while current_dist < max_dist:
            contours = measure.find_contours(distance_field, current_dist)

            for contour in contours:
                coords = []
                for pt in contour:
                    y_idx, x_idx = pt[0], pt[1]

                    # Map the fractional array indices back to physical CNC coordinates
                    px = minx + (x_idx / (res_x - 1)) * width
                    py = miny + (y_idx / (res_y - 1)) * height
                    coords.append((px, py))

                if len(coords) >= 2:
                    lines.append(LineString(coords))

            current_dist += pixel_spacing

        return lines
