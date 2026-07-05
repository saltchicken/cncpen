#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import argparse
from functools import reduce
import math
import operator
import sys
from typing import List, Tuple

from shapely import affinity
from shapely.geometry import Polygon

from cncpen import FILL_REGISTRY
from cncpen import MODIFICATION_REGISTRY
from cncpen import RenderContext
from cncpen import ImageSampler
from cncpen.cli import parse_args
from cncpen.cli import print_run_parameters
from cncpen.dxf import DXFReadError
from cncpen.dxf import extract_dxf_paths
from cncpen.geometry import _ensure_geom
from cncpen.geometry import apply_clipping
from cncpen.geometry import apply_transform
from cncpen.geometry import optimize_paths_nearest_neighbor
from cncpen.pen import PenConfig
from cncpen.pen import PenTool


def process_outlines(paths_to_draw: List[List[Tuple[float, float]]],
                     args: argparse.Namespace, pen: PenTool) -> List[Polygon]:
    """Draws outlines and extracts closed polygons to be used as fill boundaries."""
    closed_polys: List[Polygon] = []
    
    # Check if we have any fills defined in the YAML config
    has_fills = bool(getattr(args, 'job_config', {}).get('fills'))

    for pts in paths_to_draw:
        if not args.no_outline:
            pen.draw_path(pts, clearance=True)

        if has_fills and len(pts) > 2:
            dx, dy = pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]
            if math.hypot(dx, dy) < 0.01:
                poly = Polygon(pts)
                poly = poly if poly.is_valid and poly.area > 0 else poly.buffer(0)
                if poly.area > 0:
                    closed_polys.append(poly)

    return closed_polys


def process_fills(closed_polys: List[Polygon],
                  paths_to_draw: List[List[Tuple[float, float]]],
                  args: argparse.Namespace, 
                  fill_definitions: List[dict],
                  pen: PenTool) -> None:
    """Handles geometry extraction, sampling, modifications, and generation for fill patterns."""
    if not closed_polys or not fill_definitions:
        return

    try:
        combined_geom = reduce(operator.xor, closed_polys)
    except BaseException as e:
        print(f"Warning: Failed to boolean XOR boundary polygons: {e}", file=sys.stderr)
        return

    poly = _ensure_geom(combined_geom)
    if poly.is_empty or poly.area <= 0:
        return

    centroid = poly.centroid
    global_minx, global_miny, global_maxx, global_maxy = poly.bounds
    max_r = math.hypot(global_maxx - global_minx, global_maxy - global_miny) / 2.0

    all_raw_fill_coords = []

    # --- LOOP OVER EACH FILL PASS IN THE YAML CONFIG ---
    for fill_def in fill_definitions:
        pattern_name = fill_def.get("pattern")
        fill_class = FILL_REGISTRY.get(pattern_name)

        if not fill_class:
            print(f"Warning: Unknown fill pattern '{pattern_name}'", file=sys.stderr)
            continue

        filler = fill_class()
        angle = fill_def.get('angle', 0.0)

        # Create a combined namespace of global args + this specific fill's parameters
        context_args = argparse.Namespace(**vars(args), **fill_def)

        working_poly = affinity.rotate(poly, -angle, origin=centroid) if angle != 0.0 else poly

        context = RenderContext(args=context_args,
                                boundary=working_poly,
                                centroid=centroid,
                                max_r=max_r)

        # 1. Generate base lines
        lines = []
        polygons = [working_poly] if working_poly.geom_type == 'Polygon' else list(working_poly.geoms)
        for p in polygons:
            lines.extend(filler.generate(p, context))

        lines = [line for line in lines if not line.is_empty]

        # 2. Clip lines against boundary
        lines = apply_clipping(lines, boundary=working_poly)

        # 3. Apply Modification Plugins (Dynamic execution)
        for mod_name, mod_class in MODIFICATION_REGISTRY.items():
            mod = mod_class()
            if mod.is_active(context_args):
                lines = mod.apply(lines, context)

        # 4. Apply clipping again AFTER modifications
        lines = apply_clipping(lines, boundary=working_poly)

        # 5. Transform Output (Rotation & Simplify)
        lines = apply_transform(lines,
                                angle=angle,
                                origin=centroid,
                                simplify_tol=fill_def.get('simplify', 0.0))

        # Accumulate coordinates for this fill layer
        all_raw_fill_coords.extend([list(line.coords) for line in lines])

    # --- OPTIMIZE ALL LAYERS TOGETHER ---
    if not args.no_optimize and all_raw_fill_coords:
        print(f"Optimizing {len(fill_definitions)} fill layer(s)...")
        last_pos = (0.0, 0.0) if not paths_to_draw else paths_to_draw[-1][-1]
        all_raw_fill_coords = optimize_paths_nearest_neighbor(all_raw_fill_coords, start_pt=last_pos)

    # --- DRAW ---
    for f_pts in all_raw_fill_coords:
        pen.draw_path(f_pts, clearance=False)


def print_post_run_stats(output_filename: str) -> None:
    """Reads the generated file to print out runtime statistics."""
    try:
        with open(output_filename, 'r') as f:
            print(f"\nTotal G-code lines produced: {sum(1 for _ in f)}")
    except Exception as e:
        print(f"\nCould not count lines in output file: {e}")

    print(f"G-code successfully saved to {output_filename}")



def main() -> None:
    args = parse_args()
    print_run_parameters(args)

    print(f"Reading geometry from {args.dxf_file}...")

    try:
        paths_to_draw = extract_dxf_paths(
            args.dxf_file, simplify_tolerance=args.outline_simplify)
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

    with PenTool(config, output_filename=args.output) as pen:
        # 1. Process Outlines
        closed_polys = process_outlines(paths_to_draw, args, pen)
        
        # 2. Extract fills array from YAML config (default to empty list if not found)
        fill_definitions = args.job_config.get('fills', [])
        
        # 3. Process Fills (using the updated loop logic from Approach 1)
        process_fills(closed_polys, paths_to_draw, args, fill_definitions, pen)

    print_post_run_stats(args.output)


if __name__ == "__main__":
    main()
