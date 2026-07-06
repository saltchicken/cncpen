from typing import List
from shapely.geometry import LineString
from shapely.ops import unary_union

from cncpen import register_modification
from cncpen import RenderContext

@register_modification("weld")
class WeldMod:
    def apply(self, lines: List[LineString], context: RenderContext) -> List[LineString]:
        pen_width = context.config.params.get('pen_width', 0.2)
        
        # Buffer every line by half the pen width, turning them into polygons
        buffered_polys = [line.buffer(pen_width / 2.0, cap_style=2, join_style=2) for line in lines]
        
        # Melt them all into a single continuous polygon
        melted = unary_union(buffered_polys)
        
        welded_lines = []
        geoms = [melted] if melted.geom_type == 'Polygon' else list(melted.geoms)
        
        # Extract just the boundaries so the pen traces the outside edge
        for poly in geoms:
            if poly.exterior:
                welded_lines.append(LineString(poly.exterior.coords))
            for interior in poly.interiors:
                welded_lines.append(LineString(interior.coords))
                
        return welded_lines
