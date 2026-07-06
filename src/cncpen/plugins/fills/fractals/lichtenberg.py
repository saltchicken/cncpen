import argparse
import math
import random
from typing import Any, List

import argcomplete
from shapely.geometry import LineString
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill, RenderContext


@register_fill("lichtenberg")
class LichtenbergFill:
    """
    Generates a Lichtenberg-style (branching fractal) fill using an RRT
    (Rapidly-exploring Random Tree) algorithm confined to the polygon.
    """

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        spacing = context.config.params.get('spacing', 2.0)
        nodes = context.config.params.get('nodes', 1500)
        minx, miny, maxx, maxy = shape.bounds
        root = shape.centroid

        if not shape.contains(root):
            for _ in range(100):
                p = Point(random.uniform(minx, maxx),
                          random.uniform(miny, maxy))
                if shape.contains(p):
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
            if shape.contains(segment):
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

        raw_paths = build_paths(0)
        return [LineString(p) for p in raw_paths if len(p) > 1]
