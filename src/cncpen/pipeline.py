from functools import reduce
import logging
import math
import operator
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

from cncpen import OPERATION_REGISTRY
from cncpen import RenderContext
from cncpen.config import JobConfig
from cncpen.config import StepConfig
from cncpen.geometry import _ensure_geom
from cncpen.geometry import apply_clipping
from cncpen.geometry import apply_transform

logger = logging.getLogger(__name__)


def process_outlines(paths_to_draw: List[List[Tuple[float, float]]],
                     config: JobConfig) -> List[Polygon]:
    """Extracts closed polygons to be used as fill boundaries."""
    closed_polys: List[Polygon] = []
    has_fills = bool(config.fills)

    for pts in paths_to_draw:
        # Drawing logic removed; only polygon extraction remains
        if has_fills and len(pts) > 2:
            dx, dy = pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]
            if math.hypot(dx, dy) < 0.01:
                poly = Polygon(pts)
                poly = poly if poly.is_valid and poly.area > 0 else poly.buffer(0)
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
        step_config: StepConfig, active_lines: List[LineString],
        poly: Polygon) -> Tuple[BaseGeometry, List[LineString]]:
    """Determines the starting geometry based on whether previous lines are being utilized."""
    if not step_config.use_previous_lines:
        return poly, active_lines

    if not active_lines:
        logger.warning(
            "    -> 'use_previous_lines' specified, but no lines exist yet. Skipping."
        )
        return poly, active_lines

    if step_config.polygonize:
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

    remaining_lines = [] if step_config.replace_previous else active_lines
    return source_geom, remaining_lines


def _apply_operation(step_config: StepConfig, active_lines: List[LineString],
                     poly: Polygon, centroid: Point,
                     max_r: float) -> List[LineString]:
    """Handles geometry extraction, rendering context setup, and pattern generation."""
    registry_entry = OPERATION_REGISTRY.get(step_config.operation)

    if not registry_entry:
        logger.warning(f"    -> Unknown operation '{step_config.operation}'")
        return active_lines

    plugin = registry_entry["class"]()

    source_geom, remaining_lines = _prepare_source_geometry(
        step_config, active_lines, poly)

    # Setup Rotations and Context Boundaries
    working_geom = affinity.rotate(
        source_geom, -step_config.angle,
        origin=centroid) if step_config.angle != 0.0 else source_geom

    context_boundary_geom = poly.buffer(
        step_config.overscan) if step_config.overscan > 0 else poly
    context_working_boundary = affinity.rotate(
        context_boundary_geom, -step_config.angle,
        origin=centroid) if step_config.angle != 0.0 else context_boundary_geom

    context = RenderContext(config=step_config,
                            boundary=context_working_boundary,
                            centroid=centroid,
                            max_r=max_r + step_config.overscan)

    # Extract geometries to handle both single shapes and polygonized collections
    geoms = [working_geom] if working_geom.geom_type in (
        'Polygon', 'LineString', 'LinearRing') else list(getattr(working_geom, 'geoms', [working_geom]))

    if len(geoms) == 1:
        gen_shape = geoms[0].buffer(step_config.overscan) if (
            step_config.overscan > 0 and geoms[0].geom_type in ('Polygon', 'MultiPolygon')) else geoms[0]
        
        result_lines = plugin.process(remaining_lines, gen_shape, context)

        if step_config.clip_local and gen_shape.geom_type in ('Polygon', 'MultiPolygon'):
            result_lines = apply_clipping(result_lines, boundary=gen_shape)
    else:
        # For decomposed collections (from polygonize), iterate to generate fills locally
        result_lines = remaining_lines.copy()
        for g in geoms:
            gen_shape = g.buffer(step_config.overscan) if (
                step_config.overscan > 0 and g.geom_type in ('Polygon', 'MultiPolygon')) else g
            
            # Pass empty lines to isolate the generation for this specific sub-geometry
            step_lines = plugin.process([], gen_shape, context)
            
            if step_config.clip_local and gen_shape.geom_type in ('Polygon', 'MultiPolygon'):
                step_lines = apply_clipping(step_lines, boundary=gen_shape)
                
            result_lines.extend(step_lines)

    result_lines = [line for line in result_lines if not line.is_empty]

    # Final clipping and transformation back to world space
    result_lines = apply_clipping(result_lines, boundary=context_working_boundary)
    result_lines = apply_transform(result_lines,
                                   angle=step_config.angle,
                                   origin=centroid,
                                   simplify_tol=step_config.simplify)

    return result_lines


def process_fills(closed_polys: List[Polygon], config: JobConfig) -> List[LineString]:
    """Executes the pipeline of fill patterns and modifications."""
    if not closed_polys or not config.fills:
        return []

    poly = _get_boundary_polygon(closed_polys)
    if not poly:
        return []

    centroid = poly.centroid
    global_minx, global_miny, global_maxx, global_maxy = poly.bounds
    max_r = math.hypot(global_maxx - global_minx,
                       global_maxy - global_miny) / 2.0

    active_lines = []
    total_steps = len(config.fills)

    for step_idx, step_config in enumerate(config.fills, 1):

        if step_config.operation:
            logger.info(f"  [{step_idx}/{total_steps}] Executing operation '{step_config.operation}'...")
            active_lines = _apply_operation(step_config, active_lines, poly, centroid, max_r)

        else:
            logger.warning(f"  [{step_idx}/{total_steps}] Step must contain 'operation'. Ignored.")
            continue

        total_vertices = sum(len(line.coords) for line in active_lines)
        logger.info(
            f"    -> Resulting state: {len(active_lines)} lines ({total_vertices} vertices) "
        )

    # Return the generated lines instead of drawing them here
    return active_lines
