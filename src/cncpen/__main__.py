import argparse
from dataclasses import dataclass
import math
import os
import sys

from gscrib import GCodeBuilder

from .fills import *
from .utils import extract_dxf_paths


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
        self.tool_off(clearance=True)
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

    def move_to(self, x, y, clearance=False):
        self.tool_off(clearance=clearance)  # Safely ensure we are at the proper height
        self.g.rapid(x=x, y=y)

    def tool_on(self):
        # NOTE: Z axis applies pressure. Only write if not already down.
        if self.current_z != self.config.down_z:
            self.g.move(z=self.config.down_z)
            self.current_z = self.config.down_z

    def tool_off(self, clearance=False):
        # Determine our target height based on the move type
        target_z = self.config.clearance_z if clearance else self.config.rapid_z
        
        # Only lift if we are currently below the target height. 
        # (e.g., if we are already at 5.0 clearance, don't drop down to 1.0 rapid)
        if self.current_z is None or self.current_z < target_z:
            self.g.rapid(z=target_z)
            self.current_z = target_z

    def draw_path(self, points, clearance=False):
        """Draws a series of points."""
        if not points:
            return
        # Move to the start of the path using the requested clearance height
        self.move_to(*points[0], clearance=clearance)
        self.tool_on()
        for x, y in points[1:]:
            self.g.move(x=x, y=y, f=self.config.feed_rate)
        
        # Always end the path by lifting to rapid_z. 
        # If the NEXT path requires clearance, it will handle the extra lift.
        self.tool_off(clearance=False)


def main():
    parser = argparse.ArgumentParser(
        description="Generate CNC G-code from a DXF file using a pen tool.")
    parser.add_argument("dxf_file", help="Path to the input DXF file")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help=
        "Output G-code filename (default: matches input filename with .nc extension)"
    )
    parser.add_argument("--feed",
                        type=float,
                        default=400.0,
                        help="Drawing feed rate (default: 400.0)")
    parser.add_argument("--fill",
                        action="store_true",
                        help="Enable infill for closed shapes")
    parser.add_argument(
        "--pattern",
        choices=["zigzag", "sine", "concentric", "lichtenberg"],
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

    parser.add_argument("--nodes", type=int, default=1500,
                        help="Number of branches/nodes for Lichtenberg fill (default: 1500)")

    parser.add_argument("--simplify",
                        type=float,
                        default=0.2,
                        help="Simplification tolerance for fills. Higher value = fewer G-code lines (default: 0.2)")

    args = parser.parse_args()

    if args.output is None:
        base_name = os.path.splitext(args.dxf_file)[0]
        args.output = f"{base_name}.nc"

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
            # Pass clearance=True to safely hop over screws/clamps to the new entity
            pen.draw_path(pts, clearance=True)

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
                    elif args.pattern == "concentric":
                        fill_paths = generate_concentric_fill(
                            pts, spacing=args.spacing, simplify_tolerance=args.simplify)
                    elif args.pattern == "lichtenberg":
                        # Dispatch the new fill here
                        fill_paths = generate_lichtenberg_fill(
                            pts, spacing=args.spacing, nodes_count=args.nodes)
                    else:
                        fill_paths = generate_zigzag_fill(pts,
                                                          spacing=args.spacing,
                                                          angle=args.angle)

                    for f_pts in fill_paths:
                        # For fills, clearance is False. The pen will just hop 
                        # between fill lines at rapid_z.
                        pen.draw_path(f_pts, clearance=False)

    print(f"G-code successfully saved to {args.output}")


if __name__ == "__main__":
    main()
