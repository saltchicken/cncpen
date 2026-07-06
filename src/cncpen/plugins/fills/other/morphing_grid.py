import argparse
import math
from typing import Any, List

import argcomplete
from pydantic import BaseModel
from pydantic import Field
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill
from cncpen import RenderContext


class MorphingGridConfig(BaseModel):
    spacing: float = Field(default=2.0, gt=0.0)
    cell_size: float = Field(default=5.0, gt=0.0)
    morph_cycles: float = Field(default=1.0)
    sampler: Any = None


@register_fill("morphing_grid", config_class=MorphingGridConfig)
class MorphingGridFill:
    """
    Generates a grid of geometric shapes. Morphs in complexity, scale, and rotation 
    based EITHER on an underlying photo sampler OR a mathematical waveform progression.
    """

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        params = context.config.params
        spacing = params.spacing
        cell_size = params.cell_size
        morph_cycles = params.morph_cycles
        sampler = params.sampler

        minx, miny, maxx, maxy = shape.bounds
        width = maxx - minx
        height = maxy - miny

        if width == 0 or height == 0:
            return []

        step = max(spacing, cell_size)
        lines = []

        y = miny + (step / 2)
        while y <= maxy:
            x = minx + (step / 2)
            while x <= maxx:

                if sampler:
                    # Photo-Driven Mode
                    norm_phase = sampler.get_darkness(x, y)
                else:
                    # Math-Driven Mode
                    nx = (x - minx) / width
                    ny = (y - miny) / height
                    t = nx * math.cos(math.pi / 4) + ny * math.sin(math.pi / 4)
                    phase = math.sin(t * math.pi * 2 * morph_cycles)
                    norm_phase = (phase + 1) / 2.0

                sides = int(3 + (5 * norm_phase))
                radius = (step / 2.0) * (0.3 + (0.6 * norm_phase))
                rotation_rads = norm_phase * math.pi

                coords = []
                for i in range(sides + 1):
                    theta = (i * 2 * math.pi / sides) + rotation_rads
                    px = x + radius * math.cos(theta)
                    py = y + radius * math.sin(theta)
                    coords.append((px, py))

                lines.append(LineString(coords))
                x += step
            y += step

        return lines
