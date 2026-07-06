import argparse
import importlib
import os
import pkgutil

import yaml

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


def parse_args() -> dict:
    load_plugins()

    parser = argparse.ArgumentParser(
        description="Generate CNC G-code from a DXF file using a pen tool.")

    # Core required files only
    parser.add_argument("dxf_file", help="Path to the input DXF file")
    parser.add_argument("-c",
                        "--config",
                        required=True,
                        help="Path to YAML job configuration file")

    args = parser.parse_args()

    # Load the YAML config
    try:
        with open(args.config, 'r') as f:
            job_config = yaml.safe_load(f) or {}
    except Exception as e:
        parser.error(f"Failed to read YAML config: {e}")

    # Build a consolidated config dictionary
    config = job_config.get('globals', {})
    config['dxf_file'] = args.dxf_file
    config['fills'] = job_config.get('fills', [])

    if 'output' not in config:
        base_name = os.path.splitext(args.dxf_file)[0]
        config['output'] = f"{base_name}.nc"

    return config
