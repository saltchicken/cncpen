import argparse
import importlib.resources as pkg_resources
import os

import argcomplete
import yaml

from cncpen import OPERATION_REGISTRY
from cncpen.config import JobConfig
from cncpen.config import StepConfig
from cncpen.plugins import load_plugins


def get_available_presets(base_path) -> dict:
    """Recursively search for all YAML presets in the given package resource path."""
    presets = {}
    for item in base_path.iterdir():
        if item.is_dir():
            presets.update(get_available_presets(item))
        elif item.name.endswith('.yaml'):
            presets[item.name.replace('.yaml', '')] = item
    return presets


def preset_completer(prefix, parsed_args, **kwargs):
    """Provide a dictionary of preset names and descriptions for argcomplete."""
    base_path = pkg_resources.files('cncpen.presets')
    presets = get_available_presets(base_path)

    completions = {}
    for name, filepath in presets.items():
        description = "No description provided"
        try:
            # Parse the YAML file to extract the description
            config = yaml.safe_load(filepath.read_text())
            if isinstance(config, dict) and 'description' in config:
                description = config['description']
        except Exception:
            pass  # Fallback to default if the file is malformed or unreadable

        completions[name] = description

    return completions


def parse_args() -> JobConfig:
    load_plugins()

    parser = argparse.ArgumentParser(
        description="Generate CNC G-code from a DXF file using a pen tool.")

    parser.add_argument("dxf_file", help="Path to the input DXF file")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c",
                       "--config",
                       help="Path to a custom YAML job configuration file")

    # Attach the custom completer to the preset argument
    group.add_argument("-p",
                       "--preset",
                       help="Name of a built-in preset (e.g., 'contour')"
                      ).completer = preset_completer

    # Initialize argcomplete before parsing arguments
    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    job_config_raw = {}

    if args.preset:
        preset_base = pkg_resources.files('cncpen.presets')
        available_presets = get_available_presets(preset_base)
        preset_name = args.preset.replace('.yaml', '')

        if preset_name in available_presets:
            try:
                config_text = available_presets[preset_name].read_text()
                job_config_raw = yaml.safe_load(config_text) or {}
            except Exception as e:
                parser.error(f"Failed to read preset YAML: {e}")
        else:
            parser.error(
                f"Preset '{preset_name}' not found. Available presets: {', '.join(available_presets.keys())}"
            )
    else:
        try:
            with open(args.config, 'r') as f:
                job_config_raw = yaml.safe_load(f) or {}
        except Exception as e:
            parser.error(f"Failed to read custom YAML config: {e}")

    # Process and build Data Classes
    raw_globals = job_config_raw.get('globals', {})
    dxf_file = args.dxf_file
    output = raw_globals.get('output')
    if not output:
        base_name = os.path.splitext(dxf_file)[0]
        output = f"{base_name}.nc"

    fills = []
    for step in job_config_raw.get('fills', []):
        merged_dict = {**raw_globals, **step}

        operation = merged_dict.get('operation') or merged_dict.get('pattern') or merged_dict.get('modification')

        if operation and operation in OPERATION_REGISTRY:
            config_cls = OPERATION_REGISTRY[operation].get('config')
            if config_cls:
                merged_dict['params'] = config_cls(**merged_dict)

        fills.append(StepConfig(**merged_dict))

    return JobConfig(dxf_file=dxf_file,
                     output=output,
                     outline_simplify=raw_globals.get('outline_simplify', 0.0),
                     no_outline=raw_globals.get('no_outline', False),
                     feed=raw_globals.get('feed', 1200.0),
                     fills=fills,
                     globals=raw_globals)
