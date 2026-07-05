import argparse
import importlib
import os
import yaml
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

    # Core settings
    parser.add_argument("dxf_file", help="Path to the input DXF file"
    ).completer = argcomplete.completers.FilesCompleter(allowednames=(".dxf",))
    
    parser.add_argument("-c", "--config", 
                        required=True, 
                        help="Path to YAML job configuration file"
    ).completer = argcomplete.completers.FilesCompleter(allowednames=(".yaml", ".yml"))

    parser.add_argument("-o", "--output", default=None, help="Output G-code filename")
    parser.add_argument("--feed", type=float, default=1200.0, help="Drawing feed rate (default: 1200.0)")
    parser.add_argument("--no-optimize", action="store_true", help="Disable optimize algorithm")
    parser.add_argument("--outline-simplify", type=float, default=0.0, help="Simplification tolerance for outlines")
    parser.add_argument("--no-outline", action="store_true", help="Disable drawing original DXF paths")

    # Modifications (Global Modifiers)
    mod_group = parser.add_argument_group("Path Modifications (Plugins)")
    for mod_name, mod_class in MODIFICATION_REGISTRY.items():
        mod_class.setup_cli(mod_group)

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    # Load and attach the YAML config
    try:
        with open(args.config, 'r') as f:
            args.job_config = yaml.safe_load(f) or {}
    except Exception as e:
        parser.error(f"Failed to read YAML config: {e}")

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
