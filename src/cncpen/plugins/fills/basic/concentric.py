from typing import List

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill, RenderContext


@register_fill("concentric")
class ConcentricFill:

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        lines = []
        spacing = context.config.params.get('spacing', 2.0)
        ring_simplify = context.config.params.get('ring_simplify', 0.2)

        # --- INWARD CONCENTRIC (Polygons) ---
        if shape.geom_type in ('Polygon', 'MultiPolygon'):
            current_geom = shape.buffer(-spacing).simplify(
                ring_simplify, preserve_topology=False)

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

        # --- OUTWARD CONCENTRIC (LineStrings & Other Geometries) ---
        else:
            max_dist = context.max_r
            dist = spacing

            if context.config.params.get('include_base', True):
                if shape.geom_type == 'LineString':
                    lines.append(shape)
                elif hasattr(shape, 'geoms'):
                    lines.extend(
                        [g for g in shape.geoms if g.geom_type == 'LineString'])

            while dist <= max_dist:
                current_geom = shape.buffer(dist).simplify(
                    ring_simplify, preserve_topology=False)

                if current_geom.is_empty:
                    break

                polygons = [current_geom
                           ] if current_geom.geom_type == 'Polygon' else list(
                               current_geom.geoms)

                for p in polygons:
                    if p.exterior:
                        lines.append(LineString(p.exterior.coords))
                    for interior in p.interiors:
                        lines.append(LineString(interior.coords))

                dist += spacing

        return lines
