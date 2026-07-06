import math
from typing import Any, List, Tuple

from shapely import affinity
from shapely.geometry import LineString
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry


def _extract_lines(geometry: BaseGeometry) -> List[LineString]:
    """Helper to safely extract LineStrings from arbitrary Shapely geometries."""
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
    """Clips a list of lines against a bounding polygon."""
    if boundary.is_empty:
        return []

    clipped_lines = []
    for line in lines:
        intersection = boundary.intersection(line)
        clipped_lines.extend(_extract_lines(intersection))

    return clipped_lines


def apply_transform(lines: List[LineString], angle: float, origin: Any,
                    simplify_tol: float) -> List[LineString]:
    """Applies rotation and simplification to a list of lines."""
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


def _ensure_geom(shape: Any) -> Polygon:
    """Ensures a generic shape is a valid Polygon object."""
    poly = shape if isinstance(shape, BaseGeometry) else (
        Polygon() if len(shape) < 4 else Polygon(shape))
    return poly if poly.is_valid and poly.area > 0 else poly.buffer(0)
