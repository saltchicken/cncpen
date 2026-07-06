from functools import reduce
import logging
import math
import operator
import time
from typing import List, Optional, Tuple

from shapely import affinity
from shapely.geometry import GeometryCollection
from shapely.geometry import LineString
from shapely.geometry import MultiLineString
from shapely.geometry import Point
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize
from shapely.ops import unary_union

from cncpen import FILL_REGISTRY
from cncpen import MODIFICATION_REGISTRY
from cncpen import RenderContext
from cncpen.geometry import _ensure_geom
from cncpen.geometry import apply_clipping
from cncpen.geometry import apply_transform
from cncpen.pen import PenTool

logger = logging.getLogger(__name__)


def process_outlines(paths_to_draw: List[List[Tuple[float, float]]],
                     config: dict, pen: PenTool) -> List[Polygon]:
    """Draws outlines and extracts closed polygons to be used as fill boundaries."""
    closed_polys: List[Polygon] = []
    has_fills = bool(config.get('fills'))

    for pts in paths_to_draw:
        if not config.get('no_outline', False):
            pen.draw_path(pts, clearance=True)

        if has_fills and len(pts) > 2:
            dx, dy = pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]
            if math.hypot(dx, dy) < 0.01:
                poly = Polygon(pts)
                poly = poly if poly.is_valid and poly.area > 0 else poly.buffer(
                    0)
                if poly.area > 0:
                    closed_polys.append(poly)

    return closed_polys


def _get_boundary_polygon(closed_polys: List[Polygon]) -> Optional[Polygon]:
    """Combines individual closed polygons into a single master boundary."""
    try:
        combined_geom = reduce(operator.xor, closed_polys)
        poly = _ensure_geom(combined_geom)
        if poly.is_empty or poly.area <= 0:
            return None
        return poly
    except BaseException as e:
        logger.warning(f"Failed to boolean XOR boundary polygons: {e}")
        return None


def _prepare_source_geometry(
        step_def: dict, active_lines: List[LineString],
        poly: Polygon) -> Tuple[BaseGeometry, List[LineString]]:
    """Determines the starting geometry based on whether previous lines are being utilized."""
    if not step_def.get('use_previous_lines', False):
        return poly, active_lines

    if not active_lines:
        logger.warning(
            "    -> 'use_previous_lines' specified, but no lines exist yet. Skipping."
        )
        return poly, active_lines

    if step_def.get('polygonize', True):
        lines_to_node = active_lines.copy()
        if poly.boundary.geom_type == 'LineString':
            lines_to_node.append(poly.boundary)
        elif hasattr(poly.boundary, 'geoms'):
            lines_to_node.extend(list(poly.boundary.geoms))

        noded_lines = unary_union(lines_to_node)
        extracted_polys = list(polygonize(noded_lines))

        if extracted_polys:
            source_geom = GeometryCollection(extracted_polys)
            logger.info(
                f"    -> Polygonized previous lines into {len(extracted_polys)} closed regions."
            )
        else:
            logger.warning(
                "    -> Could not find closed regions to polygonize, falling back to lines."
            )
            source_geom = MultiLineString(active_lines)
    else:
        source_geom = MultiLineString(active_lines)

    remaining_lines = [] if step_def.get('replace_previous',
                                         True) else active_lines
    return source_geom, remaining_lines


def _apply_pattern(step_def: dict, step_config: dict,
                   active_lines: List[LineString], poly: Polygon,
                   centroid: Point, max_r: float) -> List[LineString]:
    """Handles geometry extraction, rendering context setup, and pattern generation."""
    pattern_name = step_def.get("pattern")
    fill_class = FILL_REGISTRY.get(pattern_name)

    if not fill_class:
        logger.warning(f"    -> Unknown fill pattern '{pattern_name}'")
        return active_lines

    filler = fill_class()
    angle = step_def.get('angle', 0.0)

    source_geom, new_active_lines = _prepare_source_geometry(
        step_def, active_lines, poly)

    # Setup Rotations and Context Boundaries
    working_geom = affinity.rotate(
        source_geom, -angle, origin=centroid) if angle != 0.0 else source_geom
    strict_master_boundary = affinity.rotate(
        poly, -angle, origin=centroid) if angle != 0.0 else poly

    overscan = step_def.get('overscan', 0.0)
    context_boundary_geom = poly.buffer(overscan) if overscan > 0 else poly
    context_working_boundary = affinity.rotate(
        context_boundary_geom, -angle,
        origin=centroid) if angle != 0.0 else context_boundary_geom

    context = RenderContext(config=step_config,
                            boundary=context_working_boundary,
                            centroid=centroid,
                            max_r=max_r + overscan)

    lines = []
    geoms = [working_geom] if working_geom.geom_type in (
        'Polygon', 'LineString', 'LinearRing') else list(working_geom.geoms)
    clip_local = step_def.get('clip_local', True)

    # Generate geometries
    for g in geoms:
        gen_shape = g.buffer(overscan) if (overscan > 0 and
                                           g.geom_type == 'Polygon') else g
        step_lines = filler.generate(gen_shape, context)

        if clip_local and g.geom_type == 'Polygon':
            step_lines = apply_clipping(step_lines, boundary=gen_shape)

        lines.extend(step_lines)

    lines = [line for line in lines if not line.is_empty]

    # Final clipping and transformation back to world space
    lines = apply_clipping(lines, boundary=context_working_boundary)
    lines = apply_transform(lines,
                            angle=angle,
                            origin=centroid,
                            simplify_tol=step_def.get('simplify', 0.0))

    new_active_lines.extend(lines)
    return new_active_lines


def _apply_modification(step_def: dict, step_config: dict,
                        active_lines: List[LineString], poly: Polygon,
                        centroid: Point, max_r: float) -> List[LineString]:
    """Applies a post-processing modification to the current active lines."""
    mod_name = step_def.get("modification")
    mod_class = MODIFICATION_REGISTRY.get(mod_name)

    if not mod_class:
        logger.warning(f"    -> Unknown modification '{mod_name}'")
        return active_lines

    mod = mod_class()
    context = RenderContext(config=step_config,
                            boundary=poly,
                            centroid=centroid,
                            max_r=max_r)

    active_lines = mod.apply(active_lines, context)
    return apply_clipping(active_lines, boundary=poly)


def process_fills(closed_polys: List[Polygon], global_config: dict,
                  fill_definitions: List[dict], pen: PenTool) -> None:
    """Executes the pipeline of fill patterns and modifications."""
    if not closed_polys or not fill_definitions:
        return

    poly = _get_boundary_polygon(closed_polys)
    if not poly:
        return

    centroid = poly.centroid
    global_minx, global_miny, global_maxx, global_maxy = poly.bounds
    max_r = math.hypot(global_maxx - global_minx,
                       global_maxy - global_miny) / 2.0

    active_lines = []
    total_steps = len(fill_definitions)

    for step_idx, step_def in enumerate(fill_definitions, 1):
        step_config = {**global_config, **step_def}
        step_timer = time.perf_counter()

        if "pattern" in step_def:
            logger.info(
                f"  [{step_idx}/{total_steps}] Executing fill pattern '{step_def['pattern']}'..."
            )
            active_lines = _apply_pattern(step_def, step_config, active_lines,
                                          poly, centroid, max_r)

        elif "modification" in step_def:
            logger.info(
                f"  [{step_idx}/{total_steps}] Applying modification '{step_def['modification']}'..."
            )
            active_lines = _apply_modification(step_def, step_config,
                                               active_lines, poly, centroid,
                                               max_r)

        else:
            logger.warning(
                f"  [{step_idx}/{total_steps}] Step must contain 'pattern' or 'modification'. Ignored."
            )
            continue

        total_vertices = sum(len(line.coords) for line in active_lines)
        logger.info(
            f"    -> Resulting state: {len(active_lines)} lines ({total_vertices} vertices) "
            f"in {time.perf_counter() - step_timer:.3f}s.")

    logger.info("  Writing fill paths to G-code...")
    for line in active_lines:
        pen.draw_path(list(line.coords), clearance=False)
