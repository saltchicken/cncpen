import argparse
from typing import List

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill
from cncpen import RenderContext


@register_fill("concentric")
class ConcentricFill:

    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--ring-simplify",
            type=float,
            default=0.2,
            help=
            "Simplification tolerance specific to inner rings (default: 0.2)")

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        lines = []
        spacing = context.args.spacing
        ring_simplify = getattr(context.args, 'ring_simplify', 0.2)

        current_geom = shape.buffer(-spacing).simplify(ring_simplify,
                                                       preserve_topology=False)

        while not current_geom.is_empty and current_geom.area > 0:
            polygons = [current_geom
                       ] if current_geom.geom_type == 'Polygon' else list(
                           current_geom.geoms)
            for p in polygons:
                if p.exterior:
                    lines.append(LineString(p.exterior.coords))
                for interior in p.interiors:
                    lines.append(LineString(interior.coords))
            current_geom = current_geom.buffer(-spacing).simplify(
                ring_simplify, preserve_topology=False)

        return lines
