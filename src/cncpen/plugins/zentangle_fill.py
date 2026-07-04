import argparse
import math
import random
from typing import List, Tuple, Any

from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry

from cncpen.fills import register_fill


@register_fill("zentangle")
class ZentangleFill:
    """
    Generates a zoned doodle fill mimicking hand-drawn zentangles.
    Partitions space into wavy regions and populates each with localized math textures.
    """

    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--density",
            type=float,
            default=2.0,
            help="Base resolution/tightness of internal textures (default: 2.0)",
        )

    def generate(self, shape: BaseGeometry, spacing: float, density: float = 2.0, **kwargs: Any) -> List[LineString]:
        minx, miny, maxx, maxy = shape.bounds
        width, height = maxx - minx, maxy - miny
        
        lines = []
        step = max(spacing, density)

        # 1. Define the wavy zone boundaries (Macro-structure)
        # We model the major dividing lines crossing the canvas diagonally
        def get_zone(x: float, y: float) -> int:
            # Normalize coordinates roughly to a 0-1 canvas space
            nx = (x - minx) / max(width, 1.0)
            ny = (y - miny) / max(height, 1.0)
            
            # Create a diagonal baseline with multiple overlapping sine waves for organic variance
            wave = (
                0.4 * math.sin(nx * 4.0) + 
                0.15 * math.sin(ny * 7.5 + nx * 2.0) + 
                0.05 * math.cos(nx * 12.0)
            )
            val = (nx + ny) / 2.0 + wave

            if val < 0.35:
                return 0  # Bottom-left: Concentric petal rings / Scales
            elif val < 0.55:
                return 1  # Lower Middle: Geometric zig-zag bands
            elif val < 0.70:
                return 2  # Upper Middle: Linear hatching with negative circles
            else:
                return 3  # Top-right: High-density swirls & organic scales

        # 2. Procedural texture synthesis across a micro-grid
        y = miny
        while y <= maxy + step:
            x = minx
            while x <= maxx + step:
                zone = get_zone(x, y)

                # ZONE 0: Organic Scales / Cobblestones
                if zone == 0:
                    # Draw overlapping arcs anchored to a grid position
                    cx, cy = x + step * 0.5, y + step * 0.5
                    scale_points = []
                    for theta in range(-30, 210, 30):
                        rad = math.radians(theta)
                        scale_points.append((cx + (step * 0.6) * math.cos(rad), cy + (step * 0.6) * math.sin(rad)))
                    lines.append(LineString(scale_points))

                # ZONE 1: Concentric Chevron / Sharp Zig-Zags
                elif zone == 1:
                    # Interlocking triangle patterns
                    if int((x // step) + (y // step)) % 2 == 0:
                        lines.append(LineString([(x, y), (x + step, y + step), (x + step * 2, y)]))
                        lines.append(LineString([(x, y + step * 0.5), (x + step, y + step * 1.5), (x + step * 2, y + step * 0.5)]))

                # ZONE 2: Linear Hatching punctuated by negative circles
                elif zone == 2:
                    # Define a persistent circle center per grid macro-block
                    cell_x = (x // (step * 4)) * (step * 4) + step * 2
                    cell_y = (y // (step * 4)) * (step * 4) + step * 2
                    dist_to_eye = math.hypot(x - cell_x, y - cell_y)
                    circle_radius = step * 1.2
                    
                    # Only draw straight crosshatch lines if we aren't inside the "eye"
                    if dist_to_eye > circle_radius:
                        lines.append(LineString([(x, y), (x + step, y + step)]))
                    else:
                        # Draw the clean rim of the circle structure
                        if abs(dist_to_eye - circle_radius) < (step * 0.5):
                            circle_outline = Point(cell_x, cell_y).buffer(circle_radius, resolution=16).exterior
                            lines.append(LineString(circle_outline.coords))

                # ZONE 3: Swirls & Spiral Fill
                elif zone == 3:
                    # Draw a tight Archimedean spiral localized inside this sector
                    spiral_points = []
                    cx, cy = x + step * 0.5, y + step * 0.5
                    # Don't overlap spirals perfectly, let them blend organically
                    max_turns = 2.5
                    for i in range(0, int(360 * max_turns), 20):
                        t = math.radians(i)
                        r = (step * 0.5) * (i / (360 * max_turns))
                        spiral_points.append((cx + r * math.cos(t), cy + r * math.sin(t)))
                    if len(spiral_points) > 1:
                        lines.append(LineString(spiral_points))

                x += step
            y += step

        # 3. Add global dividing lines to crisply separate the zones
        # This mirrors the thick, prominent black ribbon tracking across your sketchbook page
        for boundary_val in [0.35, 0.55, 0.70]:
            ribbon_pts_upper = []
            ribbon_pts_lower = []
            # Trace lines along the X axis running the equation in reverse
            for step_x in range(int(minx), int(maxx), int(step)):
                nx = (step_x - minx) / max(width, 1.0)
                wave = (
                    0.4 * math.sin(nx * 4.0) + 
                    0.15 * math.sin(((boundary_val * 2.0) - nx) * 7.5 + nx * 2.0) + 
                    0.05 * math.cos(nx * 12.0)
                )
                target_ny = (boundary_val * 2.0) - nx - 2.0 * wave
                target_y = miny + target_ny * height
                
                if miny <= target_y <= maxy:
                    ribbon_pts_lower.append((float(step_x), target_y))
                    ribbon_pts_upper.append((float(step_x), target_y + step * 0.8))
            
            if len(ribbon_pts_lower) > i:
                lines.append(LineString(ribbon_pts_lower))
                lines.append(LineString(ribbon_pts_upper))

        return lines
