import math
from typing import Any, List, Tuple

from shapely import affinity
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry


def optimize_paths_nearest_neighbor(
    paths: List[List[Tuple[float, float]]],
    start_pt: Tuple[float, float] = (0.0, 0.0)
) -> List[List[Tuple[float, float]]]:
    """Sorts paths using a greedy nearest-neighbor approach to minimize travel time."""
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
