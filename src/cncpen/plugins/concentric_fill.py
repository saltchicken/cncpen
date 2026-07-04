import argparse
import math
from typing import List, Any

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen.fills import register_fill


@register_fill("concentric")
class ConcentricFill:
    """Generates concentric (inset) fill paths."""
    
    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--ring-simplify", type=float, default=0.2, 
                            help="Simplification tolerance specific to inner rings (default: 0.2)")

    def generate(self, shape: BaseGeometry, spacing: float, ring_simplify: float = 0.2, **kwargs: Any) -> List[LineString]:
        lines = []
        current_geom = shape.buffer(-spacing).simplify(ring_simplify, preserve_topology=False)

        while not current_geom.is_empty and current_geom.area > 0:
            polygons = [current_geom] if current_geom.geom_type == 'Polygon' else list(current_geom.geoms)
            for p in polygons:
                if p.exterior:
                    lines.append(LineString(p.exterior.coords))
                for interior in p.interiors:
                    lines.append(LineString(interior.coords))
                    
            current_geom = current_geom.buffer(-spacing).simplify(ring_simplify, preserve_topology=False)

        return lines

