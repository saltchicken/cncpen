import argparse
import math
from typing import Any, List, Optional
import argcomplete
from shapely.geometry import LineString
from cncpen import register_modification, ImageSampler

@register_modification("image_mask")
class ImageMaskMod:
    @classmethod
    def setup_cli(cls, group: argparse._ArgumentGroup) -> None:
        group.add_argument("--mask-image",
                           default=None,
                           help="Optional image to modulate fill"
                          ).completer = argcomplete.completers.FilesCompleter(
                              allowednames=(".png", ".jpg", ".jpeg"))
        group.add_argument("--threshold",
                           type=float,
                           default=0.5,
                           help="Darkness cutoff")

    def is_active(self, args: argparse.Namespace) -> bool:
        return bool(getattr(args, 'mask_image', None))

    def apply(self,
              lines: List[LineString],
              args: argparse.Namespace,
              mask_sampler: Optional[ImageSampler] = None,
              **kwargs: Any) -> List[LineString]:
        if not mask_sampler:
            return lines

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
                if mask_sampler.get_darkness(pt.x, pt.y) > args.threshold:
                    current_segment.append((pt.x, pt.y))
                else:
                    if len(current_segment) > 1:
                        masked_lines.append(LineString(current_segment))
                    current_segment = []

            if len(current_segment) > 1:
                masked_lines.append(LineString(current_segment))

        return masked_lines
