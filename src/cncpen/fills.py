import math
import random
from shapely import affinity
from shapely.geometry import LineString, Polygon, Point


def generate_zigzag_fill(points, spacing, angle=0.0):
    """
    Generates back-and-forth (zig-zag) fill paths for a closed polygon.
    """
    if len(points) < 4:
        return []

    poly = Polygon(points)

    if not poly.is_valid or poly.area == 0:
        poly = poly.buffer(0)
        if poly.area == 0:
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


def generate_sinewave_fill(points,
                           spacing,
                           amplitude=1.0,
                           wavelength=5.0,
                           angle=0.0):
    """
    Generates back-and-forth sine wave fill paths for a closed polygon.
    """
    if len(points) < 4:
        return []

    poly = Polygon(points)

    if not poly.is_valid or poly.area == 0:
        poly = poly.buffer(0)
        if poly.area == 0:
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


def generate_concentric_fill(points, spacing, simplify_tolerance=0.2):
    """
    Generates concentric (inset) fill paths for a closed polygon.
    """
    if len(points) < 4:
        return []

    poly = Polygon(points)

    if not poly.is_valid or poly.area == 0:
        poly = poly.buffer(0)
        if poly.area == 0:
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

def generate_lichtenberg_fill(points, spacing, nodes_count=1000):
    """
    Generates a Lichtenberg-style (branching fractal) fill using an RRT
    (Rapidly-exploring Random Tree) algorithm confined to the polygon.
    """
    if len(points) < 4:
        return []

    poly = Polygon(points)

    if not poly.is_valid or poly.area == 0:
        poly = poly.buffer(0)
        if poly.area == 0:
            return []

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
