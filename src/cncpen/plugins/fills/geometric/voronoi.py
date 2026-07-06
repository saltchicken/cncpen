import argparse
import random
from typing import Any, List

import argcomplete
from shapely.geometry import LineString
from shapely.geometry import MultiPoint
from shapely.geometry.base import BaseGeometry
from shapely.ops import voronoi_diagram

from cncpen import register_fill, RenderContext


@register_fill("voronoi")
class VoronoiFill:
    """Generates a Voronoi diagram fill based on random or image-weighted sites."""

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        sites = context.config.params.get('sites', 500)
        sampler = context.config.params.get('sampler', None)
        minx, miny, maxx, maxy = shape.bounds
        width = maxx - minx
        height = maxy - miny

        if width == 0 or height == 0 or sites < 2:
            return []

        points = []
        attempts = 0
        max_attempts = sites * 10

        while len(points) < sites and attempts < max_attempts:
            attempts += 1
            actual_x = minx + random.uniform(0, width)
            actual_y = miny + random.uniform(0, height)

            if sampler:
                darkness = sampler.get_darkness(actual_x, actual_y)
                # Skip this point randomly if the area is light
                if random.random() > darkness:
                    continue

            points.append((actual_x, actual_y))

        if len(points) < 2:
            return []

        # 2. Compute the Voronoi diagram
        multipoint = MultiPoint(points)

        # By setting edges=True, Shapely returns the boundaries of the cells
        # as LineStrings instead of returning them as filled Polygons.
        diagram = voronoi_diagram(multipoint,
                                  envelope=shape.envelope,
                                  edges=True)

        # 3. Extract the raw lines
        lines = []
        if diagram.geom_type == 'LineString':
            lines.append(diagram)
        elif diagram.geom_type == 'MultiLineString':
            lines.extend(list(diagram.geoms))
        elif diagram.geom_type == 'GeometryCollection':
            for geom in diagram.geoms:
                if geom.geom_type == 'LineString':
                    lines.append(geom)
                elif geom.geom_type == 'MultiLineString':
                    lines.extend(list(geom.geoms))

        return lines
