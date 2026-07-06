#!/usr/bin/env python3

import math
import operator
import sys
from functools import reduce
from typing import List, Tuple

from shapely import affinity
from shapely.geometry import Polygon

from cncpen import FILL_REGISTRY
from cncpen import MODIFICATION_REGISTRY
from cncpen import RenderContext
from cncpen.cli import parse_args
from cncpen.dxf import DXFReadError
from cncpen.dxf import extract_dxf_paths
from cncpen.geometry import _ensure_geom
from cncpen.geometry import apply_clipping
from cncpen.geometry import apply_transform
from cncpen.geometry import optimize_paths_nearest_neighbor
from cncpen.pen import PenConfig
from cncpen.pen import PenTool


def process_outlines(paths_to_draw: List[List[Tuple[float, float]]],
                     config: dict, pen: PenTool) -> List[Polygon]:
    """Draws outlines and extracts closed polygons to be used as fill boundaries."""
    closed_polys: List[Polygon] = []
    
    has_fills = bool(config.get('fills'))

    for pts in paths_to_draw:
        if not config.get('no_outline', False):
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
                  global_config: dict,
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
    
    # Maintain a running pipeline of geometry
    active_lines = []

    # --- PROCESS EACH STEP IN THE YAML CONFIG SEQUENTIALLY ---
    for step_def in fill_definitions:
        # Merge global config with step parameters
        step_config = {**global_config, **step_def}

        # 1. PROCESS FILL PATTERNS
        if "pattern" in step_def:
            pattern_name = step_def.get("pattern")
            fill_class = FILL_REGISTRY.get(pattern_name)

            if not fill_class:
                print(f"Warning: Unknown fill pattern '{pattern_name}'", file=sys.stderr)
                continue

            filler = fill_class()
            angle = step_def.get('angle', 0.0)

            # Local coordinate system for the fill (rotated)
            working_poly = affinity.rotate(poly, -angle, origin=centroid) if angle != 0.0 else poly

            context = RenderContext(config=step_config,
                                    boundary=working_poly,
                                    centroid=centroid,
                                    max_r=max_r)

            # Generate base lines
            lines = []
            polygons = [working_poly] if working_poly.geom_type == 'Polygon' else list(working_poly.geoms)
            for p in polygons:
                lines.extend(filler.generate(p, context))

            lines = [line for line in lines if not line.is_empty]

            # Clip lines against rotated boundary
            lines = apply_clipping(lines, boundary=working_poly)

            # Transform Output (Rotation & Simplify) back to global space
            lines = apply_transform(lines,
                                    angle=angle,
                                    origin=centroid,
                                    simplify_tol=step_def.get('simplify', 0.0))

            # Add to our running pipeline
            active_lines.extend(lines)

        # 2. PROCESS PATH MODIFICATIONS
        elif "modification" in step_def:
            mod_name = step_def.get("modification")
            mod_class = MODIFICATION_REGISTRY.get(mod_name)
            
            if not mod_class:
                print(f"Warning: Unknown modification '{mod_name}'", file=sys.stderr)
                continue

            mod = mod_class()
            
            # Modifications run in global space against the unrotated boundary
            context = RenderContext(config=step_config,
                                    boundary=poly,
                                    centroid=centroid,
                                    max_r=max_r)

            # Apply modification to all currently accumulated lines
            active_lines = mod.apply(active_lines, context)
            
            # Clip again in case the modification pushed lines outside boundary limits
            active_lines = apply_clipping(active_lines, boundary=poly)
            
        else:
            print(f"Warning: Step must contain 'pattern' or 'modification'. Ignored: {step_def}", file=sys.stderr)

    # Accumulate finalized coordinates
    all_raw_fill_coords.extend([list(line.coords) for line in active_lines])

    # --- OPTIMIZE ALL LAYERS TOGETHER ---
    if not global_config.get('no_optimize', False) and all_raw_fill_coords:
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
    config = parse_args()

    print(f"Reading geometry from {config['dxf_file']}...")

    try:
        paths_to_draw = extract_dxf_paths(
            config['dxf_file'], simplify_tolerance=config.get('outline_simplify', 0.0))
    except DXFReadError as e:
        print(f"Fatal Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not config.get('no_optimize', False):
        print("Optimizing outline paths...")
        paths_to_draw = optimize_paths_nearest_neighbor(paths_to_draw)

    print(f"Extracted {len(paths_to_draw)} draw operations.")

    if not paths_to_draw:
        print("No drawable paths found. Exiting.")
        sys.exit(0)

    pen_config = PenConfig(feed_rate=config.get('feed', 1200.0))

    with PenTool(pen_config, output_filename=config['output']) as pen:
        # 1. Process Outlines
        closed_polys = process_outlines(paths_to_draw, config, pen)
        
        # 2. Extract fills array from YAML config (default to empty list if not found)
        fill_definitions = config.get('fills', [])
        
        # 3. Process Fills
        process_fills(closed_polys, paths_to_draw, config, fill_definitions, pen)

    print_post_run_stats(config['output'])


if __name__ == "__main__":
    main()
