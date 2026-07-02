import argparse
from dataclasses import dataclass
import math
import sys

import ezdxf
from ezdxf.path import make_path
from gscrib import GCodeBuilder

from .fills import *


@dataclass
class PenConfig:
    clearance_z: float = 5.0
    rapid_z: float = 1.0
    feed_rate: float = 400.0
    down_z: float = -1.0


class PenTool():

    def __init__(self, config: PenConfig, output_filename="output.nc"):
        self.g = GCodeBuilder(output=output_filename)
        self.config = config
        self.current_z = None  # Track the current Z height

    def __enter__(self):
        self._build_preamble()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tool_off()
        self._build_postamble()
        self.g.flush()

    def _build_preamble(self):
        self.g.set_plane('xy')
        self.g.set_distance_mode('absolute')
        self.g.set_length_units('mm')
        self.g.write("G54")  # Work Coordinate System Home

    def _build_postamble(self):
        """Writes the required final G-code commands."""
        self.g.write("M5")
        self.g.write("G17 G90")
        self.g.write("M2")

    def move_to(self, x, y):
        self.tool_off()  # Safely ensure we are at clearance_z
        self.g.rapid(x=x, y=y)

    def tool_on(self):
        # NOTE: Z axis applies pressure. Only write if not already down.
        if self.current_z != self.config.down_z:
            self.g.move(z=self.config.down_z)
            self.current_z = self.config.down_z

    def tool_off(self):
        # NOTE: Rapid lift to clearance_z to move pen tip away from stock.
        # Only write if not already at clearance.
        if self.current_z != self.config.clearance_z:
            self.g.rapid(z=self.config.clearance_z)
            self.current_z = self.config.clearance_z

    def draw_path(self, points):
        """Draws a series of points."""
        if not points:
            return
        self.move_to(*points[0])
        self.tool_on()
        for x, y in points[1:]:
            self.g.move(x=x, y=y, f=self.config.feed_rate)
        self.tool_off()


def extract_dxf_paths(filepath, flatten_distance=0.1):
    """
    Reads a DXF file and converts geometric entities into a list of point lists.
    """
    try:
        doc = ezdxf.readfile(filepath)
    except Exception as e:
        print(f"Error reading DXF file '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)

    msp = doc.modelspace()
    paths = []

    supported_types = {
        'LINE', 'LWPOLYLINE', 'POLYLINE', 'CIRCLE', 'ARC', 'ELLIPSE', 'SPLINE'
    }

    for entity in msp:
        if entity.dxftype() in supported_types:
            try:
                p = make_path(entity)
                vertices = list(p.flattening(flatten_distance))

                if vertices:
                    paths.append([(v.x, v.y) for v in vertices])
            except Exception as e:
                print(
                    f"Warning: could not process {entity.dxftype()} entity: {e}",
                    file=sys.stderr)

    return paths


def main():
    parser = argparse.ArgumentParser(
        description="Generate CNC G-code from a DXF file using a pen tool.")
    parser.add_argument("dxf_file", help="Path to the input DXF file")
    parser.add_argument("-o",
                        "--output",
                        default="output.nc",
                        help="Output G-code filename (default: output.nc)")
    parser.add_argument("--feed",
                        type=float,
                        default=400.0,
                        help="Drawing feed rate (default: 400.0)")
    parser.add_argument("--fill",
                        action="store_true",
                        help="Enable infill for closed shapes")
    parser.add_argument(
        "--pattern",
        choices=["zigzag", "sine"],
        default="zigzag",
        help="Fill pattern to use if --fill is enabled (default: zigzag)")
    parser.add_argument("--spacing",
                        type=float,
                        default=1.0,
                        help="Distance between fill lines (default: 1.0)")
    parser.add_argument("--angle",
                        type=float,
                        default=0.0,
                        help="Angle of the fill in degrees (default: 0.0)")
    parser.add_argument(
        "--amplitude",
        type=float,
        default=1.0,
        help="Amplitude for the sine wave pattern (default: 1.0)")
    parser.add_argument(
        "--wavelength",
        type=float,
        default=5.0,
        help="Wavelength for the sine wave pattern (default: 5.0)")

    args = parser.parse_args()

    print(f"Reading geometry from {args.dxf_file}...")
    paths_to_draw = extract_dxf_paths(args.dxf_file)
    print(f"Extracted {len(paths_to_draw)} draw operations.")

    if not paths_to_draw:
        print("No drawable paths found. Exiting.")
        sys.exit(0)

    config = PenConfig(feed_rate=args.feed)

    with PenTool(config, output_filename=args.output) as pen:
        for pts in paths_to_draw:
            # 1. Draw the outer boundary / standard lines
            pen.draw_path(pts)

            # 2. Draw the infill if enabled, and if the path is closed
            if args.fill and len(pts) > 2:
                dx = pts[0][0] - pts[-1][0]
                dy = pts[0][1] - pts[-1][1]

                # Check if path is closed (start and end points overlap)
                if math.hypot(dx, dy) < 0.01:
                    if args.pattern == "sine":
                        fill_paths = generate_sinewave_fill(
                            pts,
                            spacing=args.spacing,
                            amplitude=args.amplitude,
                            wavelength=args.wavelength,
                            angle=args.angle)
                    else:
                        fill_paths = generate_zigzag_fill(pts,
                                                          spacing=args.spacing,
                                                          angle=args.angle)

                    for f_pts in fill_paths:
                        pen.draw_path(f_pts)

    print(f"G-code successfully saved to {args.output}")


if __name__ == "__main__":
    main()
