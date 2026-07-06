import logging
import math
import operator
import sys
import time
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
from cncpen.pen import PenConfig
from cncpen.pen import PenTool

logger = logging.getLogger(__name__)


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
                  paths_to_draw: List[List[Tuple[float, float]]], global_config: dict,
                  fill_definitions: List[dict], pen: PenTool) -> None:
    """Handles geometry extraction, sampling, modifications, and generation for fill patterns."""
    if not closed_polys or not fill_definitions:
        return

    try:
        combined_geom = reduce(operator.xor, closed_polys)
    except BaseException as e:
        logger.warning(f"Failed to boolean XOR boundary polygons: {e}")
        return

    poly = _ensure_geom(combined_geom)
    if poly.is_empty or poly.area <= 0:
        return

    centroid = poly.centroid
    global_minx, global_miny, global_maxx, global_maxy = poly.bounds
    max_r = math.hypot(global_maxx - global_minx,
                       global_maxy - global_miny) / 2.0

    all_raw_fill_coords = []
    active_lines = []

    for step_def in fill_definitions:
        step_config = {**global_config, **step_def}

        if "pattern" in step_def:
            pattern_name = step_def.get("pattern")
            fill_class = FILL_REGISTRY.get(pattern_name)

            if not fill_class:
                logger.warning(f"Unknown fill pattern '{pattern_name}'")
                continue

            filler = fill_class()
            angle = step_def.get('angle', 0.0)

            working_poly = affinity.rotate(
                poly, -angle, origin=centroid) if angle != 0.0 else poly

            context = RenderContext(config=step_config,
                                    boundary=working_poly,
                                    centroid=centroid,
                                    max_r=max_r)

            lines = []
            polygons = [working_poly] if working_poly.geom_type == 'Polygon' else list(working_poly.geoms)
            for p in polygons:
                lines.extend(filler.generate(p, context))

            lines = [line for line in lines if not line.is_empty]
            lines = apply_clipping(lines, boundary=working_poly)
            lines = apply_transform(lines,
                                    angle=angle,
                                    origin=centroid,
                                    simplify_tol=step_def.get('simplify', 0.0))

            active_lines.extend(lines)

        elif "modification" in step_def:
            mod_name = step_def.get("modification")
            mod_class = MODIFICATION_REGISTRY.get(mod_name)

            if not mod_class:
                logger.warning(f"Unknown modification '{mod_name}'")
                continue

            mod = mod_class()

            context = RenderContext(config=step_config,
                                    boundary=poly,
                                    centroid=centroid,
                                    max_r=max_r)

            active_lines = mod.apply(active_lines, context)
            active_lines = apply_clipping(active_lines, boundary=poly)

        else:
            logger.warning(f"Step must contain 'pattern' or 'modification'. Ignored: {step_def}")

    all_raw_fill_coords.extend([list(line.coords) for line in active_lines])

    for f_pts in all_raw_fill_coords:
        pen.draw_path(f_pts, clearance=False)


def print_post_run_stats(output_filename: str) -> None:
    """Reads the generated file to log runtime statistics."""
    try:
        with open(output_filename, 'r') as f:
            logger.info(f"Total G-code lines produced: {sum(1 for _ in f)}")
    except Exception as e:
        logger.warning(f"Could not count lines in output file: {e}")

    logger.info(f"G-code successfully saved to {output_filename}")


def main() -> None:
    # Set up the base configuration for logging output
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    total_start = time.perf_counter()
    config = parse_args()

    logger.info(f"Reading geometry from {config['dxf_file']}...")
    step_start = time.perf_counter()

    try:
        paths_to_draw = extract_dxf_paths(config['dxf_file'],
                                          simplify_tolerance=config.get('outline_simplify', 0.0))
    except DXFReadError as e:
        logger.error(f"Fatal Error: {e}")
        sys.exit(1)

    logger.info(f"Extracted {len(paths_to_draw)} draw operations in {time.perf_counter() - step_start:.3f}s.")

    if not paths_to_draw:
        logger.warning("No drawable paths found. Exiting.")
        sys.exit(0)

    pen_config = PenConfig(feed_rate=config.get('feed', 1200.0))

    with PenTool(pen_config, output_filename=config['output']) as pen:
        
        logger.info("Processing outlines...")
        step_start = time.perf_counter()
        closed_polys = process_outlines(paths_to_draw, config, pen)
        logger.info(f"Outlines processed in {time.perf_counter() - step_start:.3f}s.")

        fill_definitions = config.get('fills', [])

        logger.info(f"Processing {len(fill_definitions)} fill steps...")
        step_start = time.perf_counter()
        process_fills(closed_polys, paths_to_draw, config, fill_definitions, pen)
        logger.info(f"Fills processed in {time.perf_counter() - step_start:.3f}s.")

    print_post_run_stats(config['output'])
    logger.info(f"Total execution time: {time.perf_counter() - total_start:.3f}s.")


if __name__ == "__main__":
    main()
