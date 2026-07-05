import argparse
import argcomplete
import math
from typing import Any, List, Tuple

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill

PHI = (1.0 + math.sqrt(5.0)) / 2.0


@register_fill("penrose")
class PenroseFill:
    """
    Generates an aperiodic Penrose P3 (rhombus-like) tiling pattern
    using recursive Robinson triangle deflation.
    """

    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--depth",
            type=int,
            default=5,
            help=
            "Recursion depth for triangle deflation. Higher = smaller tiles (default: 5)",
        )

    def generate(self,
                 shape: BaseGeometry,
                 depth: int = 5,
                 **kwargs: Any) -> List[LineString]:
        minx, miny, maxx, maxy = shape.bounds
        cx, cy = shape.centroid.x, shape.centroid.y

        # Calculate a safe radius to fully cover the bounding box
        dx = max(abs(maxx - cx), abs(cx - minx))
        dy = max(abs(maxy - cy), abs(cy - miny))
        radius = math.hypot(dx, dy) * 1.5

        # Initialize a sun-like wheel of 10 acute triangles around the center
        triangles = []
        for i in range(10):
            a1 = i * math.pi / 5.0
            a2 = (i + 1) * math.pi / 5.0

            p1 = (cx, cy)
            p2 = (cx + radius * math.cos(a1), cy + radius * math.sin(a1))
            p3 = (cx + radius * math.cos(a2), cy + radius * math.sin(a2))

            # Subdivide orientation alternating to form valid Penrose rhombs
            if i % 2 == 0:
                triangles.append((0, p1, p2, p3))
            else:
                triangles.append((0, p1, p3, p2))

        # Perform recursive deflation
        for _ in range(depth):
            next_triangles = []
            for t_type, p1, p2, p3 in triangles:
                if t_type == 0:
                    # Acute triangle deflation
                    # Create a new point along side p1-p2 split by the golden ratio
                    ax = p1[0] + (p2[0] - p1[0]) / PHI
                    ay = p1[1] + (p2[1] - p1[1]) / PHI
                    p_new = (ax, ay)

                    next_triangles.append((0, p3, p_new, p2))
                    next_triangles.append((1, p_new, p3, p1))
                else:
                    # Obtuse triangle deflation
                    # Create two points along sides to split the shape
                    bx = p2[0] + (p1[0] - p2[0]) / PHI
                    by = p2[1] + (p1[1] - p2[1]) / PHI
                    p_new1 = (bx, by)

                    cx = p2[0] + (p3[0] - p2[0]) / PHI
                    cy = p2[1] + (p3[1] - p2[1]) / PHI
                    p_new2 = (cx, cy)

                    next_triangles.append((1, p_new2, p_new1, p2))
                    next_triangles.append((0, p_new1, p_new2, p3))
                    next_triangles.append((1, p_new1, p3, p1))

            triangles = next_triangles

        # Extract unique line segments to avoid drawing overlapping lines twice
        seen_edges = set()
        lines = []

        def get_edge_key(
            pt1: Tuple[float, float],
            pt2: Tuple[float,
                       float]) -> Tuple[Tuple[int, int], Tuple[int, int]]:
            # Quantize coordinates to prevent floating point duplicates
            k1 = (int(round(pt1[0] * 100)), int(round(pt1[1] * 100)))
            k2 = (int(round(pt2[0] * 100)), int(round(pt2[1] * 100)))
            return (k1, k2) if k1 < k2 else (k2, k1)

        for _, p1, p2, p3 in triangles:
            for start, end in [(p1, p2), (p2, p3), (p3, p1)]:
                key = get_edge_key(start, end)
                if key not in seen_edges:
                    seen_edges.add(key)
                    lines.append(LineString([start, end]))

        return lines
