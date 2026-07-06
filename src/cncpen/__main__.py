import logging
import sys

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

    # config is now a JobConfig dataclass
    config = parse_args()

    logger.info(f"Reading geometry from {config.dxf_file}...")

    try:
        paths_to_draw = extract_dxf_paths(
            config.dxf_file, simplify_tolerance=config.outline_simplify)
    except DXFReadError as e:
        logger.error(f"Fatal Error: {e}")
        sys.exit(1)

    if not paths_to_draw:
        logger.warning("No drawable paths found. Exiting.")
        sys.exit(0)

    pen_config = PenConfig(feed_rate=config.feed)

    with PenTool(pen_config, output_filename=config.output) as pen:

        logger.info("Processing outlines...")
        closed_polys = process_outlines(paths_to_draw, config)

        if not config.no_outline:
            for pts in paths_to_draw:
                pen.draw_path(pts, clearance=True)

        logger.info(f"Processing {len(config.fills)} fill steps...")
        # Simplified process_fills signature
        fill_lines = process_fills(closed_polys, config)
        if fill_lines:
            logger.info("Writing fill paths to G-code...")
            for line in fill_lines:
                pen.draw_path(list(line.coords), clearance=False)

if __name__ == "__main__":
    main()
