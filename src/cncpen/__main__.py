# PYTHON_ARGCOMPLETE_OK

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
    load_plugins()
    args = parse_args()

    print("--- Run Parameters ---")
    for key, value in vars(args).items():
        print(f"{key}: {value}")
    print("----------------------\n")

    print(f"Reading geometry from {args.dxf_file}...")

    try:
        paths_to_draw = extract_dxf_paths(
            args.dxf_file,
            simplify_tolerance=args.outline_simplify
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

    with PenTool(config, output_filename=args.output) as pen:
        
        # --- OUTLINE DRAWING ---
        for pts in paths_to_draw:
            if not args.no_outline:
                pen.draw_path(pts, clearance=True)

            if args.pattern and len(pts) > 2:
                dx, dy = pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]
                if math.hypot(dx, dy) < 0.01:
                    poly = Polygon(pts)
                    poly = poly if poly.is_valid and poly.area > 0 else poly.buffer(0)
                    if poly.area > 0:
                        closed_polys.append(poly)

        # --- FILL DRAWING ---
        if args.pattern and closed_polys:
            combined_geom = reduce(operator.xor, closed_polys)
            fill_class = FILL_REGISTRY.get(args.pattern)
            
            if fill_class:
                filler = fill_class()
                
                # Retrieve final_strokes (List[PenStroke]) from FP core
                final_strokes = generate_pipeline(filler, combined_geom, **vars(args))
                
                # Extract raw coordinates back for hardware shell processing
                raw_fill_coords = [list(stroke.geometry.coords) for stroke in final_strokes]

                if not args.no_optimize:
                    print(f"Optimizing {args.pattern} fill paths...")
                    last_pos = (0.0, 0.0) if not paths_to_draw else paths_to_draw[-1][-1]
                    raw_fill_coords = optimize_paths_nearest_neighbor(raw_fill_coords, start_pt=last_pos)

                for f_pts in raw_fill_coords:
                    pen.draw_path(f_pts, clearance=False)

    try:
        with open(args.output, 'r') as f:
            print(f"\nTotal G-code lines produced: {sum(1 for _ in f)}")
    except Exception as e:
        print(f"\nCould not count lines in output file: {e}")

    print(f"G-code successfully saved to {args.output}")


if __name__ == "__main__":
    main()
