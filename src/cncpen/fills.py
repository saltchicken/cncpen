import importlib
from pathlib import Path
import sys

from shapely import affinity
from shapely.geometry import LineString
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

# --- REGISTRY SYSTEM ---
FILL_REGISTRY = {}


def register_fill(name):
    """Decorator to automatically register a fill pattern."""

    def decorator(func):
        FILL_REGISTRY[name] = func
        return func

    return decorator


def _ensure_geom(shape):
    """Helper to handle either a raw list of points or a Shapely geometry."""
    if isinstance(shape, BaseGeometry):
        poly = shape
    elif len(shape) < 4:
        poly = Polygon()
    else:
        poly = Polygon(shape)

    if not poly.is_valid or poly.area == 0:
        poly = poly.buffer(0)
    return poly


def _extract_lines(geometry):
    """Flattens diverse Shapely geometries into a list of LineStrings."""
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'LineString':
        return [geometry]
    elif geometry.geom_type == 'MultiLineString':
        return list(geometry.geoms)
    elif geometry.geom_type == 'GeometryCollection':
        return [g for g in geometry.geoms if g.geom_type == 'LineString']
    return []


def _apply_pattern_to_shape(shape, angle, pattern_generator, **kwargs):
    """
    Handles standard validation, rotation, and intersection logic.
    pattern_generator: A callable that takes a polygon and kwargs, 
                       returning raw Shapely LineStrings.
    """
    poly = _ensure_geom(shape)
    if poly.is_empty or poly.area == 0:
        return []

    centroid = poly.centroid
    if angle != 0.0:
        poly = affinity.rotate(poly, -angle, origin=centroid)

    polygons = [poly] if poly.geom_type == 'Polygon' else list(poly.geoms)
    all_fill_paths = []

    for p in polygons:
        raw_lines = pattern_generator(p, **kwargs)

        for line in raw_lines:
            intersection = p.intersection(line)
            clipped_lines = _extract_lines(intersection)

            for clipped in clipped_lines:
                if angle != 0.0:
                    clipped = affinity.rotate(clipped, angle, origin=centroid)
                all_fill_paths.append(list(clipped.coords))

    return all_fill_paths


@register_fill("zigzag")
def generate_zigzag_fill(shape, spacing, angle=0.0, **kwargs):
    """Generates back-and-forth (zig-zag) fill paths for a closed polygon."""

    def zigzag_generator(p, spacing):
        minx, miny, maxx, maxy = p.bounds
        y = miny + spacing
        lines = []
        left_to_right = True

        while y <= maxy:
            x1, x2 = (minx - 1, maxx + 1) if left_to_right else (maxx + 1,
                                                                 minx - 1)
            lines.append(LineString([(x1, y), (x2, y)]))
            y += spacing
            left_to_right = not left_to_right

        return lines

    return _apply_pattern_to_shape(shape,
                                   angle,
                                   zigzag_generator,
                                   spacing=spacing)


@register_fill("concentric")
def generate_concentric_fill(shape, spacing, simplify=0.2, **kwargs):
    """Generates concentric (inset) fill paths for a closed polygon."""
    poly = _ensure_geom(shape)
    if poly.is_empty or poly.area == 0:
        return []

    all_fill_paths = []
    current_geom = poly.buffer(-spacing).simplify(simplify,
                                                  preserve_topology=False)

    while not current_geom.is_empty and current_geom.area > 0:
        polygons = [
            current_geom
        ] if current_geom.geom_type == 'Polygon' else list(current_geom.geoms)

        for p in polygons:
            if p.exterior:
                all_fill_paths.append(list(p.exterior.coords))
            for interior in p.interiors:
                all_fill_paths.append(list(interior.coords))

        current_geom = current_geom.buffer(-spacing).simplify(
            simplify, preserve_topology=False)

    return all_fill_paths


def load_plugins():
    """Dynamically loads all modules in the plugins directory."""
    plugins_dir = Path(__file__).parent / "plugins"

    if not plugins_dir.exists():
        return

    for file_path in plugins_dir.glob("*.py"):
        if file_path.name == "__init__.py":
            continue

        module_name = f"cncpen.plugins.{file_path.stem}"
        try:
            importlib.import_module(module_name)
        except Exception as e:
            print(f"Warning: Failed to load plugin '{file_path.name}': {e}",
                  file=sys.stderr)
