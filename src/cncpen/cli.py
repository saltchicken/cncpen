import argparse
import os

from .fills import FILL_REGISTRY


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments and dynamically loads plugin arguments."""
    parser = argparse.ArgumentParser(
        description="Generate CNC G-code from a DXF file using a pen tool."
    )
    
    # Global arguments
    parser.add_argument("dxf_file", help="Path to the input DXF file")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output G-code filename (default: matches input filename with .nc extension)"
    )
    parser.add_argument(
        "--feed",
        type=float,
        default=400.0,
        help="Drawing feed rate (default: 400.0)"
    )
    parser.add_argument(
        "--simplify",
        type=float,
        default=0.0,
        help="Simplification tolerance for drawing paths (default: 0.0)"
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Optimize drawing order using nearest neighbor to minimize travel time"
    )

    # Subparsers for fill patterns
    subparsers = parser.add_subparsers(
        dest="pattern", 
        help="Optional: Specify a fill pattern to enable infill. If omitted, only outlines are drawn."
    )

    for name, plugin_class in FILL_REGISTRY.items():
        pattern_parser = subparsers.add_parser(name, help=f"Use the {name} fill pattern.")
        
        # Common arguments applied to all fills
        pattern_parser.add_argument(
            "--image", 
            default=None, 
            help="Optional image to modulate fill patterns with photo data"
        )
        pattern_parser.add_argument(
            "--spacing",
            type=float,
            default=1.0,
            help="Distance between fill lines (default: 1.0)"
        )
        pattern_parser.add_argument(
            "--angle",
            type=float,
            default=0.0,
            help="Angle of the fill in degrees (default: 0.0)"
        )
        pattern_parser.add_argument(
            "--fisheye",
            type=float,
            default=0.0,
            help="Apply radial distortion. Try -0.5 for a pinch, or 0.5 for a bulge. (default: 0.0)"
        )
        # Plugin-specific arguments
        plugin_class.setup_cli(pattern_parser)

    args = parser.parse_args()

    # Automatically handle the default output filename if none is provided
    if args.output is None:
        base_name = os.path.splitext(args.dxf_file)[0]
        args.output = f"{base_name}.nc"

    return args
