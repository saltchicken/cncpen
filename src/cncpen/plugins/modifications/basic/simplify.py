from typing import List

from pydantic import BaseModel
from pydantic import Field
from shapely.geometry import LineString

from cncpen import register_modification
from cncpen import RenderContext


class SimplifyConfig(BaseModel):
    tolerance: float = Field(default=0.1, ge=0.0)
    preserve_topology: bool = Field(default=False)


@register_modification("simplify", config_class=SimplifyConfig)
class SimplifyMod:

    def apply(self, lines: List[LineString],
              context: RenderContext) -> List[LineString]:
        params = context.config.params

        tolerance = params.tolerance
        preserve = params.preserve_topology

        simplified_lines = []

        for line in lines:
            if line.is_empty:
                continue

            simplified = line.simplify(tolerance, preserve_topology=preserve)

            if simplified.is_empty:
                continue
            elif simplified.geom_type == 'LineString':
                simplified_lines.append(simplified)
            elif simplified.geom_type == 'MultiLineString':
                simplified_lines.extend(list(simplified.geoms))

        return simplified_lines
