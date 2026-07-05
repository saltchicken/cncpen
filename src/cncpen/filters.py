import math
from typing import Any, List

from shapely import affinity
from shapely.geometry import LineString
from shapely.geometry import Polygon

from .pipeline import PenStroke
from .utils import roughen_line


def _extract_lines(geometry) -> List[LineString]:
    """Helper: Flattens diverse Shapely geometries into a list of LineStrings."""
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'LineString':
        return [geometry]
    elif geometry.geom_type == 'MultiLineString':
        return list(geometry.geoms)
    elif geometry.geom_type == 'GeometryCollection':
        return [g for g in geometry.geoms if g.geom_type == 'LineString']
    return []


def apply_image_mask(strokes: List[PenStroke], sampler: Any,
                     threshold: float) -> List[PenStroke]:
    masked_strokes = []
    step_res = 1.0

    for stroke in strokes:
        line = stroke.geometry
        length = line.length
        if length == 0:
            continue

        steps = max(2, int(math.ceil(length / step_res)))
        current_segment = []

        for i in range(steps + 1):
            pt = line.interpolate(i / steps, normalized=True)
            if sampler.get_darkness(pt.x, pt.y) > threshold:
                current_segment.append((pt.x, pt.y))
            else:
                if len(current_segment) > 1:
                    masked_strokes.append(
                        stroke.update_geometry(LineString(current_segment)))
                current_segment = []

        if len(current_segment) > 1:
            masked_strokes.append(
                stroke.update_geometry(LineString(current_segment)))

    return masked_strokes


def apply_roughening(strokes: List[PenStroke], amplitude: float,
                     step: float) -> List[PenStroke]:
    if amplitude <= 0.0:
        return strokes
    return [
        stroke.update_geometry(roughen_line(stroke.geometry, step, amplitude))
        for stroke in strokes
    ]


def apply_fisheye(strokes: List[PenStroke], factor: float, centroid: Any,
                  max_r: float) -> List[PenStroke]:
    if factor == 0.0 or max_r <= 0:
        return strokes

    distorted_strokes = []
    for stroke in strokes:
        line = stroke.geometry
        length = line.length
        if length == 0:
            continue

        num_segments = max(2, int(math.ceil(length / 0.5)))
        points = [
            line.interpolate(i / num_segments, normalized=True).coords[0]
            for i in range(num_segments + 1)
        ]

        warped_coords = []
        for px, py in points:
            dx, dy = px - centroid.x, py - centroid.y
            r = math.hypot(dx, dy)
            f = 1.0 + factor * ((r / max_r)**2) if r > 0 else 1.0
            warped_coords.append((centroid.x + dx * f, centroid.y + dy * f))

        distorted_strokes.append(
            stroke.update_geometry(LineString(warped_coords)))

    return distorted_strokes


def apply_clipping(strokes: List[PenStroke],
                   boundary: Polygon) -> List[PenStroke]:
    if boundary.is_empty:
        return []

    clipped_strokes = []
    for stroke in strokes:
        intersection = boundary.intersection(stroke.geometry)
        for clipped_line in _extract_lines(intersection):
            clipped_strokes.append(stroke.update_geometry(clipped_line))

    return clipped_strokes


def apply_transform(strokes: List[PenStroke], angle: float, origin: Any,
                    simplify_tol: float) -> List[PenStroke]:
    transformed_strokes = []

    for stroke in strokes:
        geom = stroke.geometry
        if angle != 0.0:
            geom = affinity.rotate(geom, angle, origin=origin)
        if simplify_tol > 0.0:
            geom = geom.simplify(simplify_tol, preserve_topology=False)

        if not geom.is_empty:
            transformed_strokes.append(stroke.update_geometry(geom))

    return transformed_strokes
