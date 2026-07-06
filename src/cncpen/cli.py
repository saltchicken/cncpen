import argparse
import importlib.resources as pkg_resources
import os
import sys

import yaml

from cncpen import FILL_REGISTRY
from cncpen import MODIFICATION_REGISTRY
from cncpen.config import JobConfig, StepConfig
from cncpen.plugins import load_plugins


def parse_args() -> JobConfig:
    load_plugins()

    parser = argparse.ArgumentParser(
        description="Generate CNC G-code from a DXF file using a pen tool.")

    parser.add_argument("dxf_file", help="Path to the input DXF file")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--config", help="Path to a custom YAML job configuration file")
    group.add_argument("-p", "--preset", help="Name of a built-in preset (e.g., 'contour')")

    args = parser.parse_args()
    job_config_raw = {}

    if args.preset:
        preset_filename = args.preset if args.preset.endswith('.yaml') else f"{args.preset}.yaml"
        try:
            config_text = pkg_resources.files('cncpen.presets').joinpath(preset_filename).read_text()
            job_config_raw = yaml.safe_load(config_text) or {}
        except FileNotFoundError:
            available = [
                f.name.replace('.yaml', '')
                for f in pkg_resources.files('cncpen.presets').iterdir()
                if f.name.endswith('.yaml')
            ]
            parser.error(f"Preset '{args.preset}' not found. Available presets: {', '.join(available)}")
        except Exception as e:
            parser.error(f"Failed to read preset YAML: {e}")
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

    # All explicitly defined dataclass properties
    known_attrs = {
        'pattern', 'modification', 'use_previous_lines', 'polygonize',
        'clip_local', 'replace_previous', 'overscan', 'simplify', 'angle'
    }

    fills = []
    for step in job_config_raw.get('fills', []):
        step_args = {}
        params = {}

        # Merge globals and step defs, identical to how pipeline previously handled it
        merged_dict = {**raw_globals, **step}

        for k, v in merged_dict.items():
            if k in known_attrs:
                step_args[k] = v
            else:
                params[k] = v

        fills.append(StepConfig(**step_args, params=params))

    return JobConfig(
        dxf_file=dxf_file,
        output=output,
        outline_simplify=raw_globals.get('outline_simplify', 0.0),
        no_outline=raw_globals.get('no_outline', False),
        feed=raw_globals.get('feed', 1200.0),
        fills=fills,
        globals=raw_globals
    )
