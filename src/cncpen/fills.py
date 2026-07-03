import math
import random
import importlib
import sys
from pathlib import Path

from shapely import affinity
from shapely.geometry import LineString, Polygon, Point
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
        # Ask the specific algorithm to generate raw lines over this polygon's bounds
        raw_lines = pattern_generator(p, **kwargs)
        
        for line in raw_lines:
            # Intersect with the polygon boundary
            intersection = p.intersection(line)
            clipped_lines = _extract_lines(intersection)

            # Handle un-rotation and coordinate extraction
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
            x1, x2 = (minx - 1, maxx + 1) if left_to_right else (maxx + 1, minx - 1)
            lines.append(LineString([(x1, y), (x2, y)]))
            y += spacing
            left_to_right = not left_to_right
            
        return lines

    return _apply_pattern_to_shape(shape, angle, zigzag_generator, spacing=spacing)


@register_fill("sine")
def generate_sinewave_fill(shape, spacing, amplitude=1.0, wavelength=5.0, angle=0.0, **kwargs):
    """Generates back-and-forth sine wave fill paths for a closed polygon."""
    
    def sinewave_generator(p, spacing, amplitude, wavelength):
        minx, miny, maxx, maxy = p.bounds
        y = miny + spacing
        lines = []
        left_to_right = True
        resolution = 0.2
        
        while y <= maxy + amplitude:
            x_start, x_end = minx - 1, maxx + 1
            wave_points = []
            num_steps = int(math.ceil((x_end - x_start) / resolution))
            
            for i in range(num_steps + 1):
                cx = x_start + i * resolution
                cy = y + amplitude * math.sin(2 * math.pi * cx / wavelength)
                wave_points.append((cx, cy))
                
            if not left_to_right:
                wave_points.reverse()
                
            lines.append(LineString(wave_points))
            y += spacing
            left_to_right = not left_to_right
            
        return lines

    return _apply_pattern_to_shape(shape, angle, sinewave_generator, 
                                   spacing=spacing, amplitude=amplitude, wavelength=wavelength)


@register_fill("sacred")
def generate_sacred_geometry_fill(shape, spacing, angle=0.0, **kwargs):
    """Generates a Flower of Life (overlapping circles) sacred geometry fill."""
    
    def sacred_generator(p, spacing):
        minx, miny, maxx, maxy = p.bounds
        radius = max(spacing, 0.1) 
        dx = radius
        dy = radius * math.sqrt(3) / 2.0
        
        # Pad the bounding box
        minx -= radius
        maxx += radius
        miny -= radius
        maxy += radius

        circles = []
        row = 0
        y = miny
        
        while y <= maxy:
            x_offset = (radius / 2.0) if (row % 2 != 0) else 0.0
            x = minx + x_offset
            while x <= maxx:
                circle_outline = Point(x, y).buffer(radius, resolution=32).exterior
                circles.append(circle_outline)
                x += dx
            y += dy
            row += 1
            
        return circles

    return _apply_pattern_to_shape(shape, angle, sacred_generator, spacing=spacing)


@register_fill("hilbert")
def generate_hilbert_fill(shape, spacing, angle=0.0, **kwargs):
    """Generates a highly intricate Hilbert space-filling curve."""
    
    def hilbert_generator(p, spacing):
        minx, miny, maxx, maxy = p.bounds
        width = maxx - minx
        height = maxy - miny
        size = max(width, height)
        safe_spacing = max(spacing, 0.1)

        if size > safe_spacing:
            order = int(math.ceil(math.log2(size / safe_spacing)))
        else:
            order = 1
        order = min(order, 8)

        def hilbert(x0, y0, xi, xj, yi, yj, n):
            if n == 0:
                return [(x0 + (xi + yi) / 2.0, y0 + (xj + yj) / 2.0)]
            
            return (
                hilbert(x0, y0, yi / 2, yj / 2, xi / 2, xj / 2, n - 1) +
                hilbert(x0 + xi / 2, y0 + xj / 2, xi / 2, xj / 2, yi / 2, yj / 2, n - 1) +
                hilbert(x0 + xi / 2 + yi / 2, y0 + xj / 2 + yj / 2, xi / 2, xj / 2, yi / 2, yj / 2, n - 1) +
                hilbert(x0 + xi / 2 + yi, y0 + xj / 2 + yj, -yi / 2, -yj / 2, -xi / 2, -xj / 2, n - 1)
            )

        pts = hilbert(minx, miny, size, 0.0, 0.0, size, order)
        if len(pts) < 2:
            return []
        return [LineString(pts)]

    return _apply_pattern_to_shape(shape, angle, hilbert_generator, spacing=spacing)


@register_fill("concentric")
def generate_concentric_fill(shape, spacing, simplify=0.2, **kwargs):
    """Generates concentric (inset) fill paths for a closed polygon."""
    poly = _ensure_geom(shape)
    if poly.is_empty or poly.area == 0:
        return []

    all_fill_paths = []
    current_geom = poly.buffer(-spacing).simplify(simplify, preserve_topology=False)

    while not current_geom.is_empty and current_geom.area > 0:
        polygons = [current_geom] if current_geom.geom_type == 'Polygon' else list(current_geom.geoms)

        for p in polygons:
            if p.exterior:
                all_fill_paths.append(list(p.exterior.coords))
            for interior in p.interiors:
                all_fill_paths.append(list(interior.coords))

        current_geom = current_geom.buffer(-spacing).simplify(simplify, preserve_topology=False)

    return all_fill_paths


@register_fill("lichtenberg")
def generate_lichtenberg_fill(shape, spacing, nodes=1000, **kwargs):
    """
    Generates a Lichtenberg-style (branching fractal) fill using an RRT
    (Rapidly-exploring Random Tree) algorithm confined to the polygon.
    """
    poly = _ensure_geom(shape)
    if poly.is_empty or poly.area == 0:
        return []

    if poly.geom_type in ('MultiPolygon', 'GeometryCollection'):
        all_paths = []
        total_area = poly.area
        for geom in poly.geoms:
            if geom.area > 0:
                island_nodes = max(10, int(nodes * (geom.area / total_area)))
                all_paths.extend(generate_lichtenberg_fill(geom, spacing, island_nodes))
        return all_paths

    minx, miny, maxx, maxy = poly.bounds

    root = poly.centroid
    if not poly.contains(root):
        for _ in range(100):
            p = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
            if poly.contains(p):
                root = p
                break

    nodes_list = [(root.x, root.y)]
    adj = {0: []}

    for _ in range(nodes):
        rx, ry = random.uniform(minx, maxx), random.uniform(miny, maxy)

        nearest_idx = 0
        min_dist_sq = float('inf')
        for i, (nx, ny) in enumerate(nodes_list):
            dist_sq = (rx - nx)**2 + (ry - ny)**2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                nearest_idx = i

        nx, ny = nodes_list[nearest_idx]
        dist = math.sqrt(min_dist_sq)

        if dist == 0:
            continue

        step = min(spacing, dist)
        new_x = nx + (rx - nx) * (step / dist)
        new_y = ny + (ry - ny) * (step / dist)

        segment = LineString([(nx, ny), (new_x, new_y)])
        if poly.contains(segment):
            new_idx = len(nodes_list)
            nodes_list.append((new_x, new_y))
            adj[nearest_idx].append(new_idx)
            adj[new_idx] = []

    def build_paths(node_idx):
        children = adj[node_idx]
        if not children:
            return [[nodes_list[node_idx]]]

        branch_paths = []
        for child_idx in children:
            child_paths = build_paths(child_idx)
            child_paths[0].insert(0, nodes_list[node_idx])
            branch_paths.extend(child_paths)
            
        return branch_paths

    return build_paths(0)


@register_fill("chaotic")
def generate_chaotic_affine_fill(shape, spacing, angle=0.0, depth=4, chaos_freq=0.15, chaos_amp=0.8, **kwargs):
    """
    Generates a highly irregular, fractal-like fill using a base motif that
    is recursively morphed using spatially-driven affine transformations.
    """
    poly = _ensure_geom(shape)
    if poly.is_empty or poly.area == 0:
        return []

    centroid = poly.centroid
    if angle != 0.0:
        poly = affinity.rotate(poly, -angle, origin=centroid)

    minx, miny, maxx, maxy = poly.bounds
    
    coarse_spacing = max(spacing * 4.0, 1.0)
    base_lines = []
    y = miny - coarse_spacing
    left_to_right = True
    while y <= maxy + coarse_spacing:
        x1, x2 = (minx - coarse_spacing, maxx + coarse_spacing) if left_to_right else (maxx + coarse_spacing, minx - coarse_spacing)
        base_lines.append(LineString([(x1, y), (x2, y)]))
        y += coarse_spacing
        left_to_right = not left_to_right

    pts = []
    for line in base_lines:
        pts.extend(list(line.coords))
    base_path = LineString(pts)

    base_motif = LineString([(0, 0), (0.3, 1.0), (0.7, -0.5), (1, 0)])

    def recursive_affine_fractal(p1, p2, current_depth, current_scale):
        if current_depth == 0:
            return [p1, p2]

        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist = math.hypot(dx, dy)
        if dist < 0.01:
            return [p1, p2]

        seg_angle = math.degrees(math.atan2(dy, dx))
        mx, my = p1[0] + dx / 2, p1[1] + dy / 2
        
        shear_x = math.sin(mx * chaos_freq) * chaos_amp
        shear_y = math.cos(my * chaos_freq) * chaos_amp
        scale_y = 1.0 + math.sin((mx + my) * (chaos_freq * 0.7)) * (chaos_amp * 0.75)

        matrix = [1.0, shear_x, shear_y, scale_y, 0.0, 0.0]
        warped_motif = affinity.affine_transform(base_motif, matrix)

        scaled = affinity.scale(warped_motif, xfact=dist, yfact=current_scale, origin=(0, 0))
        rotated = affinity.rotate(scaled, seg_angle, origin=(0, 0), use_radians=False)
        translated = affinity.translate(rotated, xoff=p1[0], yoff=p1[1])

        motif_coords = list(translated.coords)

        result_path = []
        for i in range(len(motif_coords) - 1):
            sub_path = recursive_affine_fractal(
                motif_coords[i], motif_coords[i+1], current_depth - 1, current_scale * 0.5
            )
            if i > 0:
                sub_path = sub_path[1:] 
            result_path.extend(sub_path)
        return result_path

    fractal_coords = []
    coords = list(base_path.coords)
    for i in range(len(coords) - 1):
        segment_fractal = recursive_affine_fractal(coords[i], coords[i+1], depth, coarse_spacing * 1.5)
        if i > 0:
            segment_fractal = segment_fractal[1:]
        fractal_coords.extend(segment_fractal)

    fractal_line = LineString(fractal_coords)

    polygons = [poly] if poly.geom_type == 'Polygon' else list(poly.geoms)
    all_fill_paths = []
    
    for p in polygons:
        intersection = p.intersection(fractal_line)
        clipped_lines = _extract_lines(intersection)
        
        for line in clipped_lines:
            if angle != 0.0:
                line = affinity.rotate(line, angle, origin=centroid)
            all_fill_paths.append(list(line.coords))

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
            print(f"Warning: Failed to load plugin '{file_path.name}': {e}", file=sys.stderr)
