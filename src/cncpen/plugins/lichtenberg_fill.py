import math
import random

from shapely.geometry import LineString
from shapely.geometry import Point

from cncpen.fills import _ensure_geom
from cncpen.fills import register_fill


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
                all_paths.extend(
                    generate_lichtenberg_fill(geom, spacing, island_nodes))
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
