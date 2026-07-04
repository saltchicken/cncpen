import argparse
import math
from typing import List, Any

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge

from cncpen.fills import register_fill


@register_fill("chladni")
class ChladniFill:
    """
    Generates Chladni resonant plate patterns using a marching squares algorithm.
    If an image sampler is provided, it warps the resonant nodes based on the photo's darkness.
    """
    
    handles_image_natively = True

    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--n", type=float, default=3.0,
                            help="Primary resonant frequency (default: 3.0)")
        parser.add_argument("--m", type=float, default=5.0,
                            help="Secondary resonant frequency (default: 5.0)")
        parser.add_argument("--sign", type=float, default=-1.0,
                            help="Interference mode modifier, usually 1.0 or -1.0 (default: -1.0)")
        parser.add_argument("--res", type=float, default=0.5,
                            help="Grid sampling resolution for tracing lines (default: 0.5)")

    def generate(self, shape: BaseGeometry, n: float = 3.0,
                 m: float = 5.0, sign: float = -1.0, res: float = 0.5,
                 sampler=None, simplify: float = 0.0, **kwargs: Any) -> List[LineString]:
        
        minx, miny, maxx, maxy = shape.bounds
        width = maxx - minx
        height = maxy - miny

        if width <= 0 or height <= 0:
            return []

        # Enforce a minimum resolution to prevent memory exhaustion on massive shapes
        grid_res = max(res, 0.1)

        cols = int(math.ceil(width / grid_res)) + 1
        rows = int(math.ceil(height / grid_res)) + 1

        x_grid = [minx + i * grid_res for i in range(cols)]
        y_grid = [miny + j * grid_res for j in range(rows)]

        def get_val(x: float, y: float) -> float:
            # Normalize coordinates to 0.0 - 1.0 mapping across the bounding box
            u = (x - minx) / width
            v = (y - miny) / height
            
            # Standard Chladni plate equation
            val = (math.cos(n * math.pi * u) * math.cos(m * math.pi * v) +
                   sign * math.cos(m * math.pi * u) * math.cos(n * math.pi * v))
            
            if sampler:
                # Modulate the zero-crossing threshold with the image.
                # Scaling by 2.0 allows the image darkness to significantly warp the topology.
                val += (sampler.get_darkness(x, y) - 0.5) * 2.0
                
            return val

        # Precompute the scalar field
        vals = [[get_val(x, y) for y in y_grid] for x in x_grid]

        def interp(v1: float, v2: float, p1: tuple, p2: tuple) -> tuple:
            """Linear interpolation to find the exact sub-grid zero crossing."""
            if v1 == v2:
                return p1
            t = (0.0 - v1) / (v2 - v1)
            return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))

        segments = []

        # Marching Squares Execution
        for i in range(cols - 1):
            for j in range(rows - 1):
                x0, y0 = x_grid[i], y_grid[j]
                x1, y1 = x_grid[i + 1], y_grid[j + 1]

                v00 = vals[i][j]
                v10 = vals[i + 1][j]
                v11 = vals[i + 1][j + 1]
                v01 = vals[i][j + 1]

                pts = []
                # Check for sign changes across the 4 cell edges
                if (v00 > 0) != (v10 > 0): pts.append(interp(v00, v10, (x0, y0), (x1, y0))) # Bottom
                if (v10 > 0) != (v11 > 0): pts.append(interp(v10, v11, (x1, y0), (x1, y1))) # Right
                if (v11 > 0) != (v01 > 0): pts.append(interp(v11, v01, (x1, y1), (x0, y1))) # Top
                if (v01 > 0) != (v00 > 0): pts.append(interp(v01, v00, (x0, y1), (x0, y0))) # Left

                if len(pts) == 2:
                    segments.append(LineString(pts))
                elif len(pts) == 4:
                    # Ambiguous saddle point: resolve by sampling the center average
                    center_val = (v00 + v10 + v11 + v01) / 4.0
                    if (center_val > 0) == (v00 > 0):
                        segments.append(LineString([pts[0], pts[3]]))
                        segments.append(LineString([pts[1], pts[2]]))
                    else:
                        segments.append(LineString([pts[0], pts[1]]))
                        segments.append(LineString([pts[2], pts[3]]))

        if not segments:
            return []

        # CNC Optimization: Stitch all the tiny disconnected grid segments 
        # into continuous flowing linestrings to eliminate constant pen up/down commands.
        merged = linemerge(segments)

        if simplify > 0:
            merged = merged.simplify(simplify, preserve_topology=False)
        
        continuous_lines = []
        if merged.geom_type == 'LineString':
            continuous_lines.append(merged)
        elif merged.geom_type == 'MultiLineString':
            continuous_lines.extend(list(merged.geoms))
            
        return continuous_lines
