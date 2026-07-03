import math
import random
from shapely import affinity
from shapely.geometry import LineString, Polygon, Point
from shapely.geometry.base import BaseGeometry


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


def generate_zigzag_fill(shape, spacing, angle=0.0):
    """
    Generates back-and-forth (zig-zag) fill paths for a closed polygon.
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
        minx, miny, maxx, maxy = p.bounds
        y = miny + spacing
        left_to_right = True

        while y <= maxy:
            scanline = LineString([(minx - 1, y), (maxx + 1, y)])
            intersection = p.intersection(scanline)

            if intersection.is_empty:
                y += spacing
                continue

            lines = []
            if intersection.geom_type == 'LineString':
                lines.append(intersection)
            elif intersection.geom_type == 'MultiLineString':
                lines.extend(list(intersection.geoms))
            elif intersection.geom_type == 'GeometryCollection':
                for geom in intersection.geoms:
                    if geom.geom_type == 'LineString':
                        lines.append(geom)

            if not lines:
                y += spacing
                continue

            lines.sort(key=lambda l: l.coords[0][0])
            if not left_to_right:
                lines.reverse()

            for line in lines:
                if angle != 0.0:
                    line = affinity.rotate(line, angle, origin=centroid)

                coords = list(line.coords)
                if not left_to_right:
                    coords.reverse()
                all_fill_paths.append(coords)

            left_to_right = not left_to_right
            y += spacing

    if all_fill_paths:
        all_fill_paths.pop()

    return all_fill_paths


def generate_sinewave_fill(shape,
                           spacing,
                           amplitude=1.0,
                           wavelength=5.0,
                           angle=0.0):
    """
    Generates back-and-forth sine wave fill paths for a closed polygon.
    """
    poly = _ensure_geom(shape)
    if poly.is_empty or poly.area == 0:
        return []

    centroid = poly.centroid

    if angle != 0.0:
        poly = affinity.rotate(poly, -angle, origin=centroid)

    polygons = [poly] if poly.geom_type == 'Polygon' else list(poly.geoms)
    all_fill_paths = []

    # Resolution (mm) defines how many segments make up the curve.
    # Smaller is smoother, but creates more G-code lines.
    resolution = 0.2

    for p in polygons:
        minx, miny, maxx, maxy = p.bounds
        # Pad the Y loop so waves near the top border don't get missed due to amplitude dipping
        y = miny + spacing
        left_to_right = True

        while y <= maxy + amplitude:
            x_start = minx - 1
            x_end = maxx + 1
            wave_points = []

            # Generate the sine wave scanline
            num_steps = int(math.ceil((x_end - x_start) / resolution))
            for i in range(num_steps + 1):
                cx = x_start + i * resolution
                cy = y + amplitude * math.sin(2 * math.pi * cx / wavelength)
                wave_points.append((cx, cy))

            scanline = LineString(wave_points)
            intersection = p.intersection(scanline)

            if intersection.is_empty:
                y += spacing
                continue

            lines = []
            if intersection.geom_type == 'LineString':
                lines.append(intersection)
            elif intersection.geom_type == 'MultiLineString':
                lines.extend(list(intersection.geoms))
            elif intersection.geom_type == 'GeometryCollection':
                for geom in intersection.geoms:
                    if geom.geom_type == 'LineString':
                        lines.append(geom)

            if not lines:
                y += spacing
                continue

            lines.sort(key=lambda l: l.coords[0][0])
            if not left_to_right:
                lines.reverse()

            for line in lines:
                if angle != 0.0:
                    line = affinity.rotate(line, angle, origin=centroid)

                coords = list(line.coords)
                if not left_to_right:
                    coords.reverse()
                all_fill_paths.append(coords)

            left_to_right = not left_to_right
            y += spacing

    return all_fill_paths


def generate_concentric_fill(shape, spacing, simplify_tolerance=0.2):
    """
    Generates concentric (inset) fill paths for a closed polygon.
    """
    poly = _ensure_geom(shape)
    if poly.is_empty or poly.area == 0:
        return []

    all_fill_paths = []

    # Apply simplification to the initial inset
    current_geom = poly.buffer(-spacing).simplify(simplify_tolerance, preserve_topology=False)

    while not current_geom.is_empty and current_geom.area > 0:
        polygons = [
            current_geom
        ] if current_geom.geom_type == 'Polygon' else list(current_geom.geoms)

        for p in polygons:
            if p.exterior:
                all_fill_paths.append(list(p.exterior.coords))
            for interior in p.interiors:
                all_fill_paths.append(list(interior.coords))

        # Apply simplification to subsequent insets
        current_geom = current_geom.buffer(-spacing).simplify(simplify_tolerance, preserve_topology=False)

    return all_fill_paths


def generate_lichtenberg_fill(shape, spacing, nodes_count=1000):
    """
    Generates a Lichtenberg-style (branching fractal) fill using an RRT
    (Rapidly-exploring Random Tree) algorithm confined to the polygon.
    """
    poly = _ensure_geom(shape)
    if poly.is_empty or poly.area == 0:
        return []

    # If we have disconnected islands, run the RRT on each island separately
    # so we don't get stuck failing to jump across empty voids.
    if poly.geom_type in ('MultiPolygon', 'GeometryCollection'):
        all_paths = []
        total_area = poly.area
        for geom in poly.geoms:
            if geom.area > 0:
                # Distribute the node count proportionally based on the island's area
                island_nodes = max(10, int(nodes_count * (geom.area / total_area)))
                all_paths.extend(generate_lichtenberg_fill(geom, spacing, island_nodes))
        return all_paths

    minx, miny, maxx, maxy = poly.bounds

    # 1. Find a valid starting point for the root (try centroid, or random fallback)
    root = poly.centroid
    if not poly.contains(root):
        for _ in range(100):
            p = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
            if poly.contains(p):
                root = p
                break

    nodes = [(root.x, root.y)]
    adj = {0: []}  # Adjacency list to build the tree

    # 2. Grow the tree
    for _ in range(nodes_count):
        rx, ry = random.uniform(minx, maxx), random.uniform(miny, maxy)

        # Find the nearest existing node
        nearest_idx = 0
        min_dist_sq = float('inf')
        for i, (nx, ny) in enumerate(nodes):
            dist_sq = (rx - nx)**2 + (ry - ny)**2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                nearest_idx = i

        nx, ny = nodes[nearest_idx]
        dist = math.sqrt(min_dist_sq)

        if dist == 0:
            continue

        # Step towards the random point by `spacing` distance
        step = min(spacing, dist)
        new_x = nx + (rx - nx) * (step / dist)
        new_y = ny + (ry - ny) * (step / dist)

        # Check if the new segment is entirely inside the polygon
        segment = LineString([(nx, ny), (new_x, new_y)])
        if poly.contains(segment):
            new_idx = len(nodes)
            nodes.append((new_x, new_y))
            adj[nearest_idx].append(new_idx)
            adj[new_idx] = []

    # 3. Extract continuous paths using DFS to minimize CNC pen lifts
    def build_paths(node_idx):
        children = adj[node_idx]
        if not children:
            return [[nodes[node_idx]]]

        branch_paths = []
        for child_idx in children:
            child_paths = build_paths(child_idx)
            # Prepend the parent node to the main branch path to connect them
            child_paths[0].insert(0, nodes[node_idx])
            branch_paths.extend(child_paths)
            
        return branch_paths

    return build_paths(0)

def generate_sacred_geometry_fill(shape, spacing, angle=0.0):
    """
    Generates a Flower of Life (overlapping circles) sacred geometry fill.
    The 'spacing' parameter dictates the radius of the circles.
    """
    poly = _ensure_geom(shape)
    if poly.is_empty or poly.area == 0:
        return []

    centroid = poly.centroid

    if angle != 0.0:
        poly = affinity.rotate(poly, -angle, origin=centroid)

    polygons = [poly] if poly.geom_type == 'Polygon' else list(poly.geoms)
    all_fill_paths = []

    # Prevent a 0 radius to avoid infinite loops
    radius = max(spacing, 0.1) 
    
    # Hexagonal grid dimensions
    dx = radius
    dy = radius * math.sqrt(3) / 2.0

    for p in polygons:
        minx, miny, maxx, maxy = p.bounds
        
        # Pad the bounding box to ensure the circles cover the entire polygon edge
        minx -= radius
        maxx += radius
        miny -= radius
        maxy += radius

        circles = []
        row = 0
        y = miny
        
        # Generate the overlapping grid of circles
        while y <= maxy:
            x_offset = (radius / 2.0) if (row % 2 != 0) else 0.0
            x = minx + x_offset
            while x <= maxx:
                # Create a circle outline (LinearRing). 
                # resolution=32 gives 128 points per circle for smooth CNC curves.
                circle_outline = Point(x, y).buffer(radius, resolution=32).exterior
                circles.append(circle_outline)
                x += dx
            y += dy
            row += 1

        # Intersect all generated circles with the actual polygon
        for circle in circles:
            intersection = p.intersection(circle)
            
            if intersection.is_empty:
                continue
            
            lines = []
            if intersection.geom_type == 'LineString':
                lines.append(intersection)
            elif intersection.geom_type == 'MultiLineString':
                lines.extend(list(intersection.geoms))
            elif intersection.geom_type == 'GeometryCollection':
                for geom in intersection.geoms:
                    if geom.geom_type == 'LineString':
                        lines.append(geom)

            for line in lines:
                if angle != 0.0:
                    line = affinity.rotate(line, angle, origin=centroid)
                all_fill_paths.append(list(line.coords))

    return all_fill_paths

def generate_hilbert_fill(shape, spacing, angle=0.0):
    """
    Generates a highly intricate Hilbert space-filling curve.
    Dynamically scales the fractal depth based on the bounding box and spacing.
    """
    poly = _ensure_geom(shape)
    if poly.is_empty or poly.area == 0:
        return []

    centroid = poly.centroid

    if angle != 0.0:
        poly = affinity.rotate(poly, -angle, origin=centroid)

    polygons = [poly] if poly.geom_type == 'Polygon' else list(poly.geoms)
    all_fill_paths = []

    # Prevent a 0 spacing to avoid infinite scaling loops
    safe_spacing = max(spacing, 0.1)

    for p in polygons:
        minx, miny, maxx, maxy = p.bounds
        width = maxx - minx
        height = maxy - miny
        size = max(width, height)

        # Calculate the required recursion depth (order) of the Hilbert curve
        # We want the segment lengths to roughly match the requested spacing.
        if size > safe_spacing:
            order = int(math.ceil(math.log2(size / safe_spacing)))
        else:
            order = 1
            
        # Cap the order to 8 to prevent memory exhaustion on massive shapes 
        # (Order 8 = 65,536 coordinates per polygon)
        order = min(order, 8)

        def hilbert(x0, y0, xi, xj, yi, yj, n):
            """Recursive generator for the Hilbert curve coordinates."""
            if n == 0:
                return [(x0 + (xi + yi) / 2.0, y0 + (xj + yj) / 2.0)]
            
            return (
                hilbert(x0, y0, yi / 2, yj / 2, xi / 2, xj / 2, n - 1) +
                hilbert(x0 + xi / 2, y0 + xj / 2, xi / 2, xj / 2, yi / 2, yj / 2, n - 1) +
                hilbert(x0 + xi / 2 + yi / 2, y0 + xj / 2 + yj / 2, xi / 2, xj / 2, yi / 2, yj / 2, n - 1) +
                hilbert(x0 + xi / 2 + yi, y0 + xj / 2 + yj, -yi / 2, -yj / 2, -xi / 2, -xj / 2, n - 1)
            )

        # Generate the raw curve points covering the bounding box
        pts = hilbert(minx, miny, size, 0.0, 0.0, size, order)

        if len(pts) < 2:
            continue

        # Convert to a Shapely geometry and intersect with the boundary
        curve = LineString(pts)
        intersection = p.intersection(curve)

        if intersection.is_empty:
            continue

        lines = []
        if intersection.geom_type == 'LineString':
            lines.append(intersection)
        elif intersection.geom_type == 'MultiLineString':
            lines.extend(list(intersection.geoms))
        elif intersection.geom_type == 'GeometryCollection':
            for geom in intersection.geoms:
                if geom.geom_type == 'LineString':
                    lines.append(geom)

        # Re-apply any requested rotation and save coordinates
        for line in lines:
            if angle != 0.0:
                line = affinity.rotate(line, angle, origin=centroid)
            all_fill_paths.append(list(line.coords))

    return all_fill_paths

def generate_chaotic_affine_fill(shape, spacing, angle=0.0, depth=4, chaos_freq=0.15, chaos_amp=0.8):
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
    
    # Start with coarse horizontal scanlines to guarantee overall coverage
    coarse_spacing = max(spacing * 4.0, 1.0)
    base_lines = []
    y = miny - coarse_spacing
    left_to_right = True
    while y <= maxy + coarse_spacing:
        x1, x2 = (minx - coarse_spacing, maxx + coarse_spacing) if left_to_right else (maxx + coarse_spacing, minx - coarse_spacing)
        base_lines.append(LineString([(x1, y), (x2, y)]))
        y += coarse_spacing
        left_to_right = not left_to_right

    # Link the coarse zigzag into a single path
    pts = []
    for line in base_lines:
        pts.extend(list(line.coords))
    base_path = LineString(pts)

    # The base motif to recursively apply
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
        
        # Apply the exposed parameters to the trig functions
        shear_x = math.sin(mx * chaos_freq) * chaos_amp
        shear_y = math.cos(my * chaos_freq) * chaos_amp
        
        # We offset the frequency slightly for the scale so it doesn't pulse exactly with the shear
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
        # Pass the user's requested depth here
        segment_fractal = recursive_affine_fractal(coords[i], coords[i+1], depth, coarse_spacing * 1.5)
        if i > 0:
            segment_fractal = segment_fractal[1:]
        fractal_coords.extend(segment_fractal)

    fractal_line = LineString(fractal_coords)

    # Intersect with the original boundary polygons and return the clipped paths
    polygons = [poly] if poly.geom_type == 'Polygon' else list(poly.geoms)
    all_fill_paths = []
    for p in polygons:
        intersection = p.intersection(fractal_line)
        
        if intersection.is_empty:
            continue
        
        lines = []
        if intersection.geom_type == 'LineString':
            lines.append(intersection)
        elif intersection.geom_type == 'MultiLineString':
            lines.extend(list(intersection.geoms))
        elif intersection.geom_type == 'GeometryCollection':
            for geom in intersection.geoms:
                if geom.geom_type == 'LineString':
                    lines.append(geom)

        for line in lines:
            if angle != 0.0:
                line = affinity.rotate(line, angle, origin=centroid)
            all_fill_paths.append(list(line.coords))

    return all_fill_paths
