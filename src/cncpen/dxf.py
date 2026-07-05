import sys
from pathlib import Path
from typing import List, Tuple, Union

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
        simplify_tolerance: float = 0.0) -> List[List[Tuple[float, float]]]:
    """Reads a DXF file, extracts supported entities, and converts them to 2D coordinate lists."""
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
