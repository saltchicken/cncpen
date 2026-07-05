import argparse
import importlib
import os
import pkgutil
from typing import Any

import argcomplete

from cncpen import FILL_REGISTRY
from cncpen import MODIFICATION_REGISTRY


def load_plugins() -> None:
    """Dynamically loads all plugins in the cncpen.plugins directory tree."""
    try:
        import cncpen.plugins
    except ImportError:
        return

    for _, name, is_pkg in pkgutil.walk_packages(cncpen.plugins.__path__,
                                                 cncpen.plugins.__name__ + "."):
        if not is_pkg:
            importlib.import_module(name)


def parse_args() -> argparse.Namespace:
    load_plugins()

    parser = argparse.ArgumentParser(
        description="Generate CNC G-code from a DXF file using a pen tool.")

    # Core settings (Main Parser)
    parser.add_argument(
        "dxf_file", help="Path to the input DXF file"
    ).completer = argcomplete.completers.FilesCompleter(allowednames=(".dxf",))
    parser.add_argument("-o",
                        "--output",
                        default=None,
                        help="Output G-code filename")
    parser.add_argument("--feed",
                        type=float,
                        default=1200.0,
                        help="Drawing feed rate (default: 1200.0)")
    parser.add_argument("--no-optimize",
                        action="store_true",
                        help="Disable optimize algorithm")
    parser.add_argument("--outline-simplify",
                        type=float,
                        default=0.0,
                        help="Simplification tolerance for outlines")
    parser.add_argument("--no-outline",
                        action="store_true",
                        help="Disable drawing original DXF paths")

    # Modifications (Main Parser)
    mod_group = parser.add_argument_group("Path Modifications (Plugins)")
    for mod_name, mod_class in MODIFICATION_REGISTRY.items():
        mod_class.setup_cli(mod_group)

    # Fills (Subparsers)
    subparsers = parser.add_subparsers(
        dest="pattern", help="Specify a fill pattern to enable infill.")
    for name, plugin_class in FILL_REGISTRY.items():
        pattern_parser = subparsers.add_parser(
            name, help=f"Use the {name} fill pattern.")

        # General fill arguments
        pattern_parser.add_argument("--spacing",
                                    type=float,
                                    default=2.0,
                                    help="Distance between fill lines")
        pattern_parser.add_argument("--angle",
                                    type=float,
                                    default=0.0,
                                    help="Angle of fill in degrees")
        pattern_parser.add_argument("--simplify",
                                    type=float,
                                    default=0.0,
                                    help="Simplification tolerance for fill")

        # Fill-specific arguments
        plugin_class.setup_cli(pattern_parser)

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if args.output is None:
        base_name = os.path.splitext(args.dxf_file)[0]
        args.output = f"{base_name}.nc"

    return args


def print_run_parameters(args: argparse.Namespace) -> None:
    """Prints the runtime arguments to the console."""
    print("--- Run Parameters ---")
    for key, value in vars(args).items():
        print(f"{key}: {value}")
    print("----------------------\n")
