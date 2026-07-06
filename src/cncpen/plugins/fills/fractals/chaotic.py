import argparse
import math
from typing import Any, List

import argcomplete
from shapely import affinity
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill, RenderContext


@register_fill("chaotic")
class ChaoticFill:
    """
    Generates a highly irregular, fractal-like fill using a base motif that
    is recursively morphed using spatially-driven affine transformations.
    """

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        spacing = context.config.params.get('spacing', 2.0)
        depth = context.config.params.get('depth', 4)
        chaos_freq = context.config.params.get('chaos_freq', 0.15)
        chaos_amp = context.config.params.get('chaos_amp', 0.8)

        minx, miny, maxx, maxy = shape.bounds
        coarse_spacing = max(spacing * 4.0, 1.0)
        base_lines = []
        y = miny - coarse_spacing
        left_to_right = True

        while y <= maxy + coarse_spacing:
            x1, x2 = (minx - coarse_spacing, maxx +
                      coarse_spacing) if left_to_right else (maxx +
                                                             coarse_spacing,
                                                             minx -
                                                             coarse_spacing)
            base_lines.append(LineString([(x1, y), (x2, y)]))
            y += coarse_spacing
            left_to_right = not left_to_right

        pts = []
        for line in base_lines:
            pts.extend(list(line.coords))
        base_path = LineString(pts)

        base_motif = LineString([(0, 0), (0.3, 1.0), (0.7, -0.5), (1, 0)])

        def recursive_affine_fractal(p1, p2, current_depth, current_scale):
            if current_depth == 0:
                return [p1, p2]

            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            dist = math.hypot(dx, dy)
            if dist < 0.01:
                return [p1, p2]

            seg_angle = math.degrees(math.atan2(dy, dx))
            mx, my = p1[0] + dx / 2, p1[1] + dy / 2

            shear_x = math.sin(mx * chaos_freq) * chaos_amp
            shear_y = math.cos(my * chaos_freq) * chaos_amp
            scale_y = 1.0 + math.sin(
                (mx + my) * (chaos_freq * 0.7)) * (chaos_amp * 0.75)

            matrix = [1.0, shear_x, shear_y, scale_y, 0.0, 0.0]
            warped_motif = affinity.affine_transform(base_motif, matrix)

            scaled = affinity.scale(warped_motif,
                                    xfact=dist,
                                    yfact=current_scale,
                                    origin=(0, 0))
            rotated = affinity.rotate(scaled,
                                      seg_angle,
                                      origin=(0, 0),
                                      use_radians=False)
            translated = affinity.translate(rotated, xoff=p1[0], yoff=p1[1])

            motif_coords = list(translated.coords)

            result_path = []
            for i in range(len(motif_coords) - 1):
                sub_path = recursive_affine_fractal(motif_coords[i],
                                                    motif_coords[i + 1],
                                                    current_depth - 1,
                                                    current_scale * 0.5)
                if i > 0:
                    sub_path = sub_path[1:]
                result_path.extend(sub_path)
            return result_path

        fractal_coords = []
        coords = list(base_path.coords)
        for i in range(len(coords) - 1):
            segment_fractal = recursive_affine_fractal(coords[i], coords[i + 1],
                                                       depth,
                                                       coarse_spacing * 1.5)
            if i > 0:
                segment_fractal = segment_fractal[1:]
            fractal_coords.extend(segment_fractal)

        return [LineString(fractal_coords)]
