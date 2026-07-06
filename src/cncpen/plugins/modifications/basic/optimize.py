from typing import List

from shapely.geometry import LineString

from cncpen import register_modification
from cncpen import RenderContext
from cncpen.geometry import optimize_paths_nearest_neighbor


@register_modification("optimize")
class OptimizeMod:

    def apply(self, lines: List[LineString],
              context: RenderContext) -> List[LineString]:
        if not lines:
            return []

        # 1. Convert Shapely LineStrings into coordinate lists
        raw_paths = [list(line.coords) for line in lines]

        # 2. Grab optional starting coordinates from the config, defaulting to origin
        start_x = context.config.get('start_x', 0.0)
        start_y = context.config.get('start_y', 0.0)

        # 3. Pass to the existing nearest-neighbor optimizer
        optimized_paths = optimize_paths_nearest_neighbor(raw_paths,
                                                          start_pt=(start_x,
                                                                    start_y))

        # 4. Convert back to Shapely LineStrings
        return [LineString(path) for path in optimized_paths]
