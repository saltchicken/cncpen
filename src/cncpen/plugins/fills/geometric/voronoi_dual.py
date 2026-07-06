import argparse
from typing import Any, List

import argcomplete
import numpy as np
from pydantic import BaseModel
from pydantic import Field
from scipy.spatial import Delaunay
from scipy.spatial import Voronoi
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill
from cncpen import RenderContext


class VoronoiDualConfig(BaseModel):
    spacing: float = Field(default=2.0, gt=0.0)
    num_points: int = Field(default=0, ge=0)
    seed: int = Field(default=42)
    mode: str = Field(default='dual')


@register_fill("voronoi-dual", config_class=VoronoiDualConfig)
class VoronoiDualFill:
    """Generates Voronoi cells, Delaunay triangulations, or both overlaid."""

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        params = context.config.params
        spacing = params.spacing
        num_points = params.num_points
        seed = params.seed
        mode = params.mode
        lines = []
        minx, miny, maxx, maxy = shape.bounds
        width = maxx - minx
        height = maxy - miny

        if width <= 0 or height <= 0:
            return []

        if num_points <= 0:
            area = width * height
            safe_spacing = max(0.2, spacing)
            num_points = max(4, int(area / (safe_spacing**2)))

        # Expand generation bounds slightly so that Voronoi ridges don't
        # prematurely terminate before hitting the true clipping boundary.
        margin_x = width * 0.1
        margin_y = height * 0.1

        np.random.seed(seed)
        xs = np.random.uniform(minx - margin_x, maxx + margin_x, num_points)
        ys = np.random.uniform(miny - margin_y, maxy + margin_y, num_points)
        points = np.column_stack((xs, ys))

        # Both diagrams require a minimum of 4 distinct points
        if len(points) < 4:
            return []

        # 1. Generate Voronoi Edges
        if mode in ["voronoi", "dual"]:
            vor = Voronoi(points)
            for ridge in vor.ridge_vertices:
                if -1 not in ridge:  # -1 represents a ridge stretching to infinity
                    p1 = vor.vertices[ridge[0]]
                    p2 = vor.vertices[ridge[1]]
                    lines.append(LineString([p1, p2]))

        # 2. Generate Delaunay Triangulation Edges
        if mode in ["delaunay", "dual"]:
            tri = Delaunay(points)
            delaunay_edges = set()

            # Extract unique edges from the simplices (triangles)
            for simplex in tri.simplices:
                for i in range(3):
                    idx1 = simplex[i]
                    idx2 = simplex[(i + 1) % 3]
                    # Sort the vertex indices so (A, B) and (B, A) hash to the same tuple
                    delaunay_edges.add(tuple(sorted([idx1, idx2])))

            for edge in delaunay_edges:
                p1 = points[edge[0]]
                p2 = points[edge[1]]
                lines.append(LineString([p1, p2]))

        return lines
