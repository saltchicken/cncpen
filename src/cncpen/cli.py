import argparse
import importlib.resources as pkg_resources
import os
import sys

import yaml

from cncpen import FILL_REGISTRY
from cncpen import MODIFICATION_REGISTRY
from cncpen.plugins import load_plugins


def parse_args() -> dict:
    load_plugins()

    parser = argparse.ArgumentParser(
        description="Generate CNC G-code from a DXF file using a pen tool.")

    parser.add_argument("dxf_file", help="Path to the input DXF file")

    # Create a group so the user must provide EITHER a config OR a preset
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c",
                       "--config",
                       help="Path to a custom YAML job configuration file")
    group.add_argument("-p",
                       "--preset",
                       help="Name of a built-in preset (e.g., 'contour')")

    args = parser.parse_args()
    job_config = {}

    # Logic to load either from the bundled presets or a local file
    if args.preset:
        preset_filename = args.preset if args.preset.endswith(
            '.yaml') else f"{args.preset}.yaml"
        try:
            # Access the bundled YAML file directly from the package
            config_text = pkg_resources.files('cncpen.presets').joinpath(
                preset_filename).read_text()
            job_config = yaml.safe_load(config_text) or {}
        except FileNotFoundError:
            # Give a helpful error showing what presets actually exist
            available = [
                f.name.replace('.yaml', '')
                for f in pkg_resources.files('cncpen.presets').iterdir()
                if f.name.endswith('.yaml')
            ]
            parser.error(
                f"Preset '{args.preset}' not found. Available presets: {', '.join(available)}"
            )
        except Exception as e:
            parser.error(f"Failed to read preset YAML: {e}")
    else:
        try:
            with open(args.config, 'r') as f:
                job_config = yaml.safe_load(f) or {}
        except Exception as e:
            parser.error(f"Failed to read custom YAML config: {e}")

    # Build a consolidated config dictionary
    config = job_config.get('globals', {})
    config['dxf_file'] = args.dxf_file
    config['fills'] = job_config.get('fills', [])

    if 'output' not in config:
        base_name = os.path.splitext(args.dxf_file)[0]
        config['output'] = f"{base_name}.nc"

    return config
