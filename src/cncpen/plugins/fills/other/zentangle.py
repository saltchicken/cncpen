import argparse
import math
from typing import Any, List

import argcomplete
from shapely.geometry import LineString
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill, RenderContext


@register_fill("zentangle")
class ZentangleFill:
    """
    Generates a zoned doodle fill.
    If an image is provided, brightness dictates the pattern zone, creating a shaded portrait.
    Otherwise, defaults to wavy mathematical bands.
    """

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        spacing = context.config.params.get('spacing', 2.0)
        density = context.config.params.get('density', 3.0)
        sampler = context.config.params.get('sampler', None)
        minx, miny, maxx, maxy = shape.bounds
        width, height = maxx - minx, maxy - miny

        lines = []
        step = max(spacing, density)

        def get_zone(x: float, y: float) -> int:
            """Determines which texture to draw based on either the image or math."""
            if sampler:
                # Image-Driven Mode
                darkness = sampler.get_darkness(x, y)
                if darkness < 0.15:
                    return -1  # Too light, leave blank
                elif darkness < 0.45:
                    return 0  # Light texture
                elif darkness < 0.75:
                    return 1  # Medium texture
                else:
                    return 2  # Dark texture
            else:
                # Math-Driven Mode (Wavy Bands)
                nx = (x - minx) / max(width, 1.0)
                ny = (y - miny) / max(height, 1.0)
                wave = 0.4 * math.sin(
                    nx * 4.0) + 0.15 * math.sin(ny * 7.5 + nx * 2.0)
                val = (nx + ny) / 2.0 + wave

                if val < 0.4:
                    return 0
                elif val < 0.65:
                    return 1
                else:
                    return 2

        y = miny
        while y <= maxy + step:
            x = minx
            while x <= maxx + step:
                zone = get_zone(x, y)

                # Skip drawing in pure white areas (highlights)
                if zone == -1:
                    x += step
                    continue

                cx, cy = x + step * 0.5, y + step * 0.5

                # ZONE 0: Open Circles (Light Shading)
                if zone == 0:
                    # Draw a simple circle in the center of the cell
                    radius = step * 0.35
                    circle = Point(cx, cy).buffer(radius,
                                                  resolution=12).exterior
                    lines.append(LineString(circle.coords))

                # ZONE 1: Overlapping Scales/Petals (Medium Shading)
                elif zone == 1:
                    # Draw a 180-degree arc mimicking fish scales or roof tiles
                    scale_points = []
                    for theta in range(0, 181, 30):
                        rad = math.radians(theta)
                        scale_points.append((cx + (step * 0.6) * math.cos(rad),
                                             cy + (step * 0.6) * math.sin(rad)))
                    lines.append(LineString(scale_points))

                # ZONE 2: Dense Spirals (Dark Shading)
                elif zone == 2:
                    # Draw a tight spiral to fill the grid cell heavily with ink
                    spiral_points = []
                    max_turns = 3.0
                    for i in range(0, int(360 * max_turns), 30):
                        t = math.radians(i)
                        # Spiral grows outwards
                        r = (step * 0.45) * (i / (360 * max_turns))
                        spiral_points.append(
                            (cx + r * math.cos(t), cy + r * math.sin(t)))

                    if len(spiral_points) > 1:
                        lines.append(LineString(spiral_points))

                x += step
            y += step

        return lines
