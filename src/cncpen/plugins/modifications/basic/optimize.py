from typing import List

from shapely.geometry import LineString

from cncpen import register_modification, RenderContext
from cncpen.geometry import optimize_paths_nearest_neighbor


@register_modification("optimize")
class OptimizeMod:

    def apply(self, lines: List[LineString],
              context: RenderContext) -> List[LineString]:
        if not lines:
            return []

        raw_paths = [list(line.coords) for line in lines]

        start_x = context.config.params.get('start_x', 0.0)
        start_y = context.config.params.get('start_y', 0.0)

        optimized_paths = optimize_paths_nearest_neighbor(
            raw_paths, start_pt=(start_x, start_y)
        )

        return [LineString(path) for path in optimized_paths]
