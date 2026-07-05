#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import argparse
from dataclasses import dataclass
from functools import reduce
import importlib
import math
import operator
import os
from pathlib import Path
import pkgutil
import sys
from typing import Any, List, Optional, Tuple, Union

import argcomplete
import ezdxf
from ezdxf.path import make_path
from gscrib import GCodeBuilder
from shapely import affinity
from shapely.geometry import LineString
from shapely.geometry import MultiLineString
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge

# Import API from __init__.py
from cncpen import FILL_REGISTRY, MODIFICATION_REGISTRY, ImageSampler

class DXFReadError(Exception):
    """Raised when a DXF file cannot be successfully read or parsed."""
    pass


def load_plugins() -> None:
    """Dynamically loads all plugins in the cncpen.plugins directory tree."""
    try:
        import cncpen.plugins
    except ImportError:
        return

    # Walk through all modules in the plugins package and load them
    for _, name, is_pkg in pkgutil.walk_packages(cncpen.plugins.__path__, cncpen.plugins.__name__ + "."):
        if not is_pkg:
            importlib.import_module(name)


def extract_dxf_paths(
        filepath: Union[str, Path],
        flatten_distance: float = 0.1,
        simplify_tolerance: float = 0.0) -> List[List[Tuple[float, float]]]:
    try:
        doc = ezdxf.readfile(filepath)
    except Exception as e:
        raise DXFReadError(f"Error reading DXF file '{filepath}': {e}") from e

    msp = doc.modelspace()
    raw_lines: List[LineString] = []
    supported_types = {
        'LINE', 'LWPOLYLINE', 'POLYLINE', 'CIRCLE', 'ARC', 'ELLIPSE', 'SPLINE'
    }

    for entity in msp:
        if entity.dxftype() in supported_types:
            try:
                p = make_path(entity)
                vertices = list(p.flattening(flatten_distance))
                if len(vertices) > 1:
                    raw_lines.append(LineString([(v.x, v.y) for v in vertices]))
            except Exception as e:
                print(
                    f"Warning: could not process {entity.dxftype()} entity: {e}",
                    file=sys.stderr)

    if not raw_lines:
        return []

    merged_geometry = linemerge(raw_lines)
    if simplify_tolerance > 0:
        merged_geometry = merged_geometry.simplify(simplify_tolerance,
                                                   preserve_topology=True)

    paths: List[List[Tuple[float, float]]] = []
    if isinstance(merged_geometry, LineString):
        paths.append(list(merged_geometry.coords))
    elif isinstance(merged_geometry, MultiLineString):
        for line in merged_geometry.geoms:
            paths.append(list(line.coords))

    return paths


def optimize_paths_nearest_neighbor(
    paths: List[List[Tuple[float, float]]],
    start_pt: Tuple[float, float] = (0.0, 0.0)
) -> List[List[Tuple[float, float]]]:
    if not paths:
        return []

    unvisited = list(paths)
    optimized: List[List[Tuple[float, float]]] = []
    current_pt = start_pt

    def dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    while unvisited:
        best_idx = -1
        best_dist = float('inf')
        reverse_best = False

        for i, path in enumerate(unvisited):
            if not path:
                continue
            d_start = dist(current_pt, path[0])
            if d_start < best_dist:
                best_dist = d_start
                best_idx = i
                reverse_best = False

            d_end = dist(current_pt, path[-1])
            if d_end < best_dist:
                best_dist = d_end
                best_idx = i
                reverse_best = True

        if best_idx == -1:
            break

        chosen_path = unvisited.pop(best_idx)
        if reverse_best:
            chosen_path = list(reversed(chosen_path))

        optimized.append(chosen_path)
        current_pt = chosen_path[-1]

    return optimized


def _extract_lines(geometry: BaseGeometry) -> List[LineString]:
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'LineString':
        return [geometry]
    elif geometry.geom_type == 'MultiLineString':
        return list(geometry.geoms)
    elif geometry.geom_type == 'GeometryCollection':
        return [g for g in geometry.geoms if g.geom_type == 'LineString']
    return []


def apply_clipping(lines: List[LineString],
                   boundary: BaseGeometry) -> List[LineString]:
    if boundary.is_empty:
        return []

    clipped_lines = []
    for line in lines:
        intersection = boundary.intersection(line)
        clipped_lines.extend(_extract_lines(intersection))

    return clipped_lines


def apply_transform(lines: List[LineString], angle: float, origin: Any,
                    simplify_tol: float) -> List[LineString]:
    transformed_lines = []
    for line in lines:
        geom = line
        if angle != 0.0:
            geom = affinity.rotate(geom, angle, origin=origin)
        if simplify_tol > 0.0:
            geom = geom.simplify(simplify_tol, preserve_topology=False)
        if not geom.is_empty:
            transformed_lines.append(geom)

    return transformed_lines


def _ensure_geom(shape):
    poly = shape if isinstance(shape, BaseGeometry) else (
        Polygon() if len(shape) < 4 else Polygon(shape))
    return poly if poly.is_valid and poly.area > 0 else poly.buffer(0)


@dataclass
class PenConfig:
    clearance_z: float = 5.0
    rapid_z: float = 1.0
    feed_rate: float = 400.0
    down_z: float = -1.0


class PenTool:
    def __init__(self,
                 config: PenConfig,
                 output_filename: str = "output.nc") -> None:
        self.g = GCodeBuilder(output=output_filename)
        self.config = config
        self.current_z: Optional[float] = None

    def __enter__(self) -> "PenTool":
        self._build_preamble()
        return self

    def __exit__(self, exc_type: type, exc_val: Exception,
                 exc_tb: type) -> None:
        self.tool_off(clearance=True)
        self._build_postamble()
        self.g.flush()

    def _build_preamble(self) -> None:
        self.g.set_plane('xy')
        self.g.set_distance_mode('absolute')
        self.g.set_length_units('mm')
        self.g.write("G54")
        self.g.write(f"F{self.config.feed_rate}")
        self.g.rapid(z=self.config.clearance_z)
        self.current_z = self.config.clearance_z

    def _build_postamble(self) -> None:
        self.g.write("M5")
        self.g.write("G17 G90")
        self.g.write("M2")

    def move_to(self, x: float, y: float, clearance: bool = False) -> None:
        self.tool_off(clearance=clearance)
        self.g.rapid(x=x, y=y)

    def tool_on(self) -> None:
        if self.current_z != self.config.down_z:
            self.g.move(z=self.config.down_z)
            self.current_z = self.config.down_z

    def tool_off(self, clearance: bool = False) -> None:
        target_z = self.config.clearance_z if clearance else self.config.rapid_z
        if self.current_z is None or self.current_z < target_z:
            self.g.rapid(z=target_z)
            self.current_z = target_z

    def draw_path(self,
                  points: List[Tuple[float, float]],
                  clearance: bool = False) -> None:
        if not points:
            return
        self.move_to(*points[0], clearance=clearance)
        self.tool_on()
        for x, y in points[1:]:
            self.g.move(x=x, y=y, f=self.config.feed_rate)
        self.tool_off(clearance=False)


def parse_args() -> argparse.Namespace:
    # Discover and register all plugins automatically before building the parser
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
                                    default=1.0,
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


def main() -> None:
    args = parse_args()

    print("--- Run Parameters ---")
    for key, value in vars(args).items():
        print(f"{key}: {value}")
    print("----------------------\n")

    print(f"Reading geometry from {args.dxf_file}...")

    try:
        paths_to_draw = extract_dxf_paths(
            args.dxf_file, simplify_tolerance=args.outline_simplify)
    except DXFReadError as e:
        print(f"Fatal Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not args.no_optimize:
        print("Optimizing outline paths...")
        paths_to_draw = optimize_paths_nearest_neighbor(paths_to_draw)

    print(f"Extracted {len(paths_to_draw)} draw operations.")

    if not paths_to_draw:
        print("No drawable paths found. Exiting.")
        sys.exit(0)

    config = PenConfig(feed_rate=args.feed)
    closed_polys: List[Polygon] = []

    with PenTool(config, output_filename=args.output) as pen:

        # --- OUTLINE DRAWING ---
        for pts in paths_to_draw:
            if not args.no_outline:
                pen.draw_path(pts, clearance=True)

            if args.pattern and len(pts) > 2:
                dx, dy = pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]
                if math.hypot(dx, dy) < 0.01:
                    poly = Polygon(pts)
                    poly = poly if poly.is_valid and poly.area > 0 else poly.buffer(0)
                    if poly.area > 0:
                        closed_polys.append(poly)

        # --- FILL DRAWING ---
        if args.pattern and closed_polys:
            combined_geom = reduce(operator.xor, closed_polys)
            fill_class = FILL_REGISTRY.get(args.pattern)

            if fill_class:
                filler = fill_class()

                # Setup base geometry constraints
                poly = _ensure_geom(combined_geom)
                if not poly.is_empty and poly.area > 0:
                    centroid = poly.centroid
                    angle = getattr(args, 'angle', 0.0)

                    working_poly = affinity.rotate(
                        poly, -angle, origin=centroid) if angle != 0.0 else poly
                    global_minx, global_miny, global_maxx, global_maxy = working_poly.bounds
                    max_r = math.hypot(global_maxx - global_minx,
                                       global_maxy - global_miny) / 2.0

                    fill_img_path = getattr(args, 'image', None)
                    fill_sampler = ImageSampler(
                        fill_img_path,
                        working_poly.bounds) if fill_img_path else None

                    mask_img_path = getattr(args, 'mask_image', None)
                    mask_sampler = ImageSampler(
                        mask_img_path,
                        working_poly.bounds) if mask_img_path else None

                    # 1. Generate base lines
                    lines = []
                    polygons = [
                        working_poly
                    ] if working_poly.geom_type == 'Polygon' else list(
                        working_poly.geoms)
                    for p in polygons:
                        lines.extend(
                            filler.generate(p,
                                            sampler=fill_sampler,
                                            **vars(args)))

                    lines = [line for line in lines if not line.is_empty]

                    # 2. Apply Modification Plugins (Hardcoded execution order)
                    hardcoded_mod_pipeline = [
                        "image_mask", "roughen", "fisheye"
                    ]

                    for mod_name in hardcoded_mod_pipeline:
                        mod_class = MODIFICATION_REGISTRY.get(mod_name)
                        if mod_class:
                            mod = mod_class()
                            if mod.is_active(args):
                                lines = mod.apply(lines=lines,
                                                  args=args,
                                                  mask_sampler=mask_sampler,
                                                  centroid=centroid,
                                                  max_r=max_r)

                    # 3. Core Geometric Filters (Clipping & Transform)
                    lines = apply_clipping(lines, boundary=working_poly)
                    lines = apply_transform(lines,
                                            angle=angle,
                                            origin=centroid,
                                            simplify_tol=getattr(
                                                args, 'simplify', 0.0))

                    final_lines = lines
                else:
                    final_lines = []

                raw_fill_coords = [list(line.coords) for line in final_lines]

                if not args.no_optimize and raw_fill_coords:
                    print(f"Optimizing {args.pattern} fill paths...")
                    last_pos = (0.0, 0.0) if not paths_to_draw else paths_to_draw[-1][-1]
                    raw_fill_coords = optimize_paths_nearest_neighbor(
                        raw_fill_coords, start_pt=last_pos)

                for f_pts in raw_fill_coords:
                    pen.draw_path(f_pts, clearance=False)

    try:
        with open(args.output, 'r') as f:
            print(f"\nTotal G-code lines produced: {sum(1 for _ in f)}")
    except Exception as e:
        print(f"\nCould not count lines in output file: {e}")

    print(f"G-code successfully saved to {args.output}")


if __name__ == "__main__":
    main()
