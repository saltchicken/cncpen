import logging
import math
import sys
import time
from typing import List, Tuple

from shapely.geometry import Polygon

from cncpen.cli import parse_args
from cncpen.dxf import DXFReadError
from cncpen.dxf import extract_dxf_paths
from cncpen.pen import PenConfig
from cncpen.pen import PenTool
from cncpen.pipeline import process_fills

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
        process_fills(closed_polys, config, fill_definitions, pen)
        logger.info(f"Fills processed in {time.perf_counter() - step_start:.3f}s.")

    print_post_run_stats(config['output'])
    logger.info(f"Total execution time: {time.perf_counter() - total_start:.3f}s.")


if __name__ == "__main__":
    main()
