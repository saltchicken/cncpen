import math
import sys

import ezdxf
from ezdxf.path import make_path
from shapely.geometry import LineString
from shapely.geometry import MultiLineString
from shapely.ops import linemerge


def extract_dxf_paths(filepath, flatten_distance=0.1, simplify_tolerance=0.0):
    """
    Reads a DXF file, flattens entities, and stitches disconnected 
    segments together to heal poor SVG-to-DXF conversions.
    """
    try:
        doc = ezdxf.readfile(filepath)
    except Exception as e:
        print(f"Error reading DXF file '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)

    msp = doc.modelspace()
    raw_lines = []

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
                    file=sys.stderr)

    if not raw_lines:
        return []

    # 2. Stitch touching line segments together
    merged_geometry = linemerge(raw_lines)

    # NEW: Apply simplification if a tolerance is provided
    if simplify_tolerance > 0:
        merged_geometry = merged_geometry.simplify(simplify_tolerance,
                                                   preserve_topology=True)

    paths = []

    # 3. Format back into point lists for the CNC pen
    if isinstance(merged_geometry, LineString):
        paths.append(list(merged_geometry.coords))
    elif isinstance(merged_geometry, MultiLineString):
        for line in merged_geometry.geoms:
            paths.append(list(line.coords))

    return paths


def optimize_paths_nearest_neighbor(paths, start_pt=(0.0, 0.0)):
    """
    Optimizes drawing order using a greedy nearest neighbor algorithm to
    minimize travel distance. Reverses paths if the end point is closer.
    """
    if not paths:
        return []

    unvisited = list(paths)
    optimized = []
    current_pt = start_pt

    def dist(p1, p2):
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
