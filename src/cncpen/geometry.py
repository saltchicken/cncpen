import math
from typing import Any, List, Tuple
import numpy as np
from scipy.spatial import cKDTree

from shapely import affinity
from shapely.geometry import LineString
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry


def optimize_paths_nearest_neighbor(
    paths: List[List[Tuple[float, float]]],
    start_pt: Tuple[float, float] = (0.0, 0.0)
) -> List[List[Tuple[float, float]]]:
    """
    Sorts paths using a greedy nearest-neighbor approach to minimize travel time.
    Utilizes a KD-Tree for O(N log N) spatial querying of endpoints.
    """
    if not paths:
        return []

    # Filter out empty paths to ensure coordinate extraction doesn't crash
    valid_paths = [p for p in paths if p]
    n_paths = len(valid_paths)
    if n_paths == 0:
        return []

    # Flatten start and end points into a single array for the KDTree
    # Index format: even = start point, odd = end point
    endpoints = np.zeros((n_paths * 2, 2))
    for i, path in enumerate(valid_paths):
        endpoints[i * 2] = path[0]        # Start point
        endpoints[i * 2 + 1] = path[-1]   # End point

    # Build the spatial index
    tree = cKDTree(endpoints)
    visited = np.zeros(n_paths, dtype=bool)
    optimized: List[List[Tuple[float, float]]] = []
    current_pt = np.array(start_pt)

    for _ in range(n_paths):
        k = 16  # Initial search batch size
        best_idx = -1
        
        while best_idx == -1:
            query_k = min(k, n_paths * 2)
            distances, indices = tree.query(current_pt, k=query_k)
            
            # Scipy returns scalars if k=1, but arrays if k>1
            if query_k == 1:
                distances, indices = [distances], [indices]
                
            for dist, idx in zip(distances, indices):
                path_idx = idx // 2
                if not visited[path_idx]:
                    best_idx = idx
                    break
            
            if best_idx == -1:
                # If all 'k' nearest neighbors were already visited, expand search ring
                if query_k == n_paths * 2:
                    break  # Should only hit this if logic fails or floats corrupt
                k *= 4

        if best_idx == -1:
            break

        # Decode the point index back to the path and direction
        path_idx = best_idx // 2
        is_end = (best_idx % 2 != 0)
        
        chosen_path = valid_paths[path_idx]
        if is_end:
            chosen_path = list(reversed(chosen_path))
            
        optimized.append(chosen_path)
        visited[path_idx] = True
        
        # Update current position to the exit point of the chosen path
        current_pt = np.array(chosen_path[-1])

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
