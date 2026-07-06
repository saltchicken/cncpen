from typing import List

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from pydantic import BaseModel, Field

from cncpen import register_fill
from cncpen import RenderContext


class ConcentricConfig(BaseModel):
    spacing: float = Field(default=2.0, gt=0.0)
    ring_simplify: float = Field(default=0.2, ge=0.0)
    include_base: bool = Field(default=True)


@register_fill("concentric", config_class=ConcentricConfig)
class ConcentricFill:

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        lines = []
        params = context.config.params
        spacing = params.spacing
        ring_simplify = params.ring_simplify

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

            if params.include_base:
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
