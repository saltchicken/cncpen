from typing import List

from shapely.geometry import LineString

from cncpen import register_modification
from cncpen import RenderContext


@register_modification("simplify")
class SimplifyMod:

    def apply(self, lines: List[LineString],
              context: RenderContext) -> List[LineString]:

        # Pull settings from the YAML config, falling back to safe defaults
        tolerance = context.config.get('tolerance', 0.1)
        preserve = context.config.get('preserve_topology', False)

        simplified_lines = []

        for line in lines:
            if line.is_empty:
                continue

            # Apply the Douglas-Peucker simplification algorithm
            simplified = line.simplify(tolerance, preserve_topology=preserve)

            # Shapely's simplify can occasionally collapse complex lines into
            # MultiLineStrings if preserve_topology is False. We handle both cases.
            if simplified.is_empty:
                continue
            elif simplified.geom_type == 'LineString':
                simplified_lines.append(simplified)
            elif simplified.geom_type == 'MultiLineString':
                simplified_lines.extend(list(simplified.geoms))

        return simplified_lines
