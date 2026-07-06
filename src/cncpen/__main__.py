import logging
import sys
import time

from cncpen.cli import parse_args
from cncpen.dxf import DXFReadError
from cncpen.dxf import extract_dxf_paths
from cncpen.pen import PenConfig
from cncpen.pen import PenTool
from cncpen.pipeline import process_fills
from cncpen.pipeline import process_outlines

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%H:%M:%S')
    logging.getLogger('ezdxf').setLevel(logging.WARNING)

    total_start = time.perf_counter()
    
    # config is now a JobConfig dataclass
    config = parse_args()

    logger.info(f"Reading geometry from {config.dxf_file}...")
    step_start = time.perf_counter()

    try:
        paths_to_draw = extract_dxf_paths(config.dxf_file, simplify_tolerance=config.outline_simplify)
    except DXFReadError as e:
        logger.error(f"Fatal Error: {e}")
        sys.exit(1)

    logger.info(
        f"Extracted {len(paths_to_draw)} draw operations in {time.perf_counter() - step_start:.3f}s."
    )

    if not paths_to_draw:
        logger.warning("No drawable paths found. Exiting.")
        sys.exit(0)

    pen_config = PenConfig(feed_rate=config.feed)

    with PenTool(pen_config, output_filename=config.output) as pen:

        logger.info("Processing outlines...")
        step_start = time.perf_counter()
        closed_polys = process_outlines(paths_to_draw, config, pen)
        logger.info(f"Outlines processed in {time.perf_counter() - step_start:.3f}s.")

        logger.info(f"Processing {len(config.fills)} fill steps...")
        step_start = time.perf_counter()
        # Simplified process_fills signature
        process_fills(closed_polys, config, pen)
        logger.info(f"Fills processed in {time.perf_counter() - step_start:.3f}s.")

    logger.info(f"Total execution time: {time.perf_counter() - total_start:.3f}s.")


if __name__ == "__main__":
    main()
