import math
import sys
from pathlib import Path
from typing import List, Tuple, Union
import random

import ezdxf
from ezdxf.path import make_path
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge


class DXFReadError(Exception):
    """Raised when a DXF file cannot be successfully read or parsed."""
    pass


def extract_dxf_paths(
    filepath: Union[str, Path], 
    flatten_distance: float = 0.1, 
    simplify_tolerance: float = 0.0
) -> List[List[Tuple[float, float]]]:
    """
    Reads a DXF file, flattens entities, and stitches disconnected 
    segments together to heal poor SVG-to-DXF conversions.
    """
    try:
        doc = ezdxf.readfile(filepath)
    except Exception as e:
        # Raise a custom exception instead of a hard process exit
        raise DXFReadError(f"Error reading DXF file '{filepath}': {e}") from e

    msp = doc.modelspace()
    raw_lines: List[LineString] = []

    supported_types = {
        'LINE', 'LWPOLYLINE', 'POLYLINE', 'CIRCLE', 'ARC', 'ELLIPSE', 'SPLINE'
    }

    # 1. Extract everything as raw Shapely LineStrings
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
                    file=sys.stderr
                )

    if not raw_lines:
        return []

    # 2. Stitch touching line segments together
    merged_geometry = linemerge(raw_lines)

    # 3. Apply simplification if a tolerance is provided
    if simplify_tolerance > 0:
        merged_geometry = merged_geometry.simplify(
            simplify_tolerance,
            preserve_topology=True
        )

    paths: List[List[Tuple[float, float]]] = []

    # 4. Format back into point lists for the CNC pen
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
    """
    Optimizes drawing order using a greedy nearest neighbor algorithm to
    minimize travel distance. Reverses paths if the end point is closer.
    """
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

            # Check distance to start of path
            d_start = dist(current_pt, path[0])
            if d_start < best_dist:
                best_dist = d_start
                best_idx = i
                reverse_best = False

            # Check distance to end of path (allows drawing backwards)
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
        # Update our current position to the end of the drawn path
        current_pt = chosen_path[-1]

    return optimized

def roughen_line(line: LineString, segment_length: float = 1.0, amplitude: float = 0.2) -> LineString:
    """Subdivides a line and applies Gaussian noise perpendicular to the path."""
    if line.length <= segment_length:
        return line

    num_segments = max(1, int(math.ceil(line.length / segment_length)))
    points = [line.interpolate(i / num_segments, normalized=True).coords[0] for i in range(num_segments + 1)]

    if len(points) < 3:
        return line

    wiggled_coords = [points[0]]

    for i in range(1, len(points) - 1):
        px, py = points[i - 1]
        nx, ny = points[i + 1]
        
        dx, dy = nx - px, ny - py
        length = math.hypot(dx, dy)
        
        if length == 0:
            wiggled_coords.append(points[i])
            continue
            
        norm_x, norm_y = -dy / length, dx / length
        displacement = random.gauss(0, amplitude)
        
        wiggled_coords.append((points[i][0] + norm_x * displacement, points[i][1] + norm_y * displacement))

    wiggled_coords.append(points[-1])
    return LineString(wiggled_coords)

def roughen_coords(points: List[Tuple[float, float]], segment_length: float, amplitude: float) -> List[Tuple[float, float]]:
    """Wrapper to safely apply roughening directly to raw coordinate lists."""
    if amplitude <= 0 or len(points) < 2:
        return points
        
    line = LineString(points)
    return list(roughen_line(line, segment_length, amplitude).coords)
