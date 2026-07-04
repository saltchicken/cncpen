import math
import operator
import sys
from functools import reduce
from typing import List

from shapely.geometry import Polygon

from .cli import parse_args
from .fills import FILL_REGISTRY, load_plugins, generate_pipeline
from .machine import PenConfig, PenTool
from .utils import DXFReadError, extract_dxf_paths, optimize_paths_nearest_neighbor


def main() -> None:
    # 1. Load all dynamic plugins to populate the registry
    load_plugins()

    # 2. Parse arguments via isolated CLI module
    args = parse_args()

    print(f"Reading geometry from {args.dxf_file}...")

    # 3. Handle geometry extraction with the new custom exception
    try:
        paths_to_draw = extract_dxf_paths(
            args.dxf_file
            # Removed simplify_tolerance here as it now targets the fill plugins
        )
    except DXFReadError as e:
        print(f"Fatal Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not args.no_optimize:
        print("Optimizing outline paths...")
        paths_to_draw = optimize_paths_nearest_neighbor(paths_to_draw)

    print(f"Extracted {len(paths_to_draw)} draw operations.")

    if not paths_to_draw:
        print("No drawable paths found. Exiting.")
        sys.exit(0)

    config = PenConfig(feed_rate=args.feed)
    closed_polys: List[Polygon] = []

    # 4. Orchestrate the G-code generation
    with PenTool(config, output_filename=args.output) as pen:
        
        # Draw all outlines and collect closed shapes
        for pts in paths_to_draw:
            pen.draw_path(pts, clearance=True)

            # Collect closed shapes if a fill pattern was requested
            if args.pattern and len(pts) > 2:
                dx = pts[0][0] - pts[-1][0]
                dy = pts[0][1] - pts[-1][1]

                # Check if path is closed (start and end points overlap)
                if math.hypot(dx, dy) < 0.01:
                    poly = Polygon(pts)
                    if poly.is_valid and poly.area > 0:
                        closed_polys.append(poly)
                    else:
                        poly = poly.buffer(0)  # Attempt to fix self-intersections
                        if poly.area > 0:
                            closed_polys.append(poly)

        # Process Fills using the Even-Odd Rule
        if args.pattern and closed_polys:
            # XOR all closed paths to automatically punch out holes
            combined_geom = reduce(operator.xor, closed_polys)

            fill_class = FILL_REGISTRY.get(args.pattern)
            if fill_class:
                filler = fill_class()
                
                # Delegate to the central pipeline
                # **vars(args) will seamlessly pass 'simplify' down to the pipeline
                fill_paths = generate_pipeline(
                    filler, 
                    combined_geom, 
                    **vars(args)
                )

                if not args.no_optimize:
                    print(f"Optimizing {args.pattern} fill paths...")
                    last_position = (0.0, 0.0) if not paths_to_draw else paths_to_draw[-1][-1]
                    fill_paths = optimize_paths_nearest_neighbor(
                        fill_paths, start_pt=last_position
                    )

                for f_pts in fill_paths:
                    pen.draw_path(f_pts, clearance=False)

    print(f"G-code successfully saved to {args.output}")


if __name__ == "__main__":
    main()
