import math
from typing import List

from shapely.geometry import LineString

from cncpen import ImageSampler
from cncpen import register_modification
from cncpen import RenderContext


@register_modification("image_mask")
class ImageMaskMod:

    def apply(self, lines: List[LineString],
              context: RenderContext) -> List[LineString]:

        mask_image = context.config.params.get('mask_image')
        if not mask_image:
            return lines

        mask_sampler = ImageSampler(mask_image, context.bounds)
        threshold = context.config.params.get('threshold', 0.5)
        masked_lines = []
        step_res = 1.0

        for line in lines:
            length = line.length
            if length == 0:
                continue

            steps = max(2, int(math.ceil(length / step_res)))
            current_segment = []

            for i in range(steps + 1):
                pt = line.interpolate(i / steps, normalized=True)
                if mask_sampler.get_darkness(pt.x, pt.y) > threshold:
                    current_segment.append((pt.x, pt.y))
                else:
                    if len(current_segment) > 1:
                        masked_lines.append(LineString(current_segment))
                    current_segment = []

            if len(current_segment) > 1:
                masked_lines.append(LineString(current_segment))

        return masked_lines
