import argparse
import math
from typing import List, Any

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen.fills import _apply_pattern_to_shape
from cncpen.fills import register_fill


@register_fill("morphing_grid")
class MorphingGridFill:
    """
    Generates a grid of geometric shapes that morph in complexity (sides),
    scale, and rotation across the geometry to simulate a waveform progression over time.
    """
    
    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--cell-size", type=float, default=5.0,
                            help="Size of the bounding grid for each morphing cell (default: 5.0)")
        parser.add_argument("--morph-cycles", type=float, default=1.0,
                            help="Number of complete waveform morph cycles across the shape (default: 1.0)")

    def generate(self, shape: BaseGeometry, spacing: float, cell_size: float = 5.0, 
                 morph_cycles: float = 1.0, angle: float = 0.0, **kwargs: Any) -> List[List[tuple[float, float]]]:
        
        def morph_generator(p, spacing):
            minx, miny, maxx, maxy = p.bounds
            width = maxx - minx
            height = maxy - miny

            if width == 0 or height == 0:
                return []

            # Use the larger of the global spacing or the specific cell size
            step = max(spacing, cell_size)
            lines = []

            y = miny + (step / 2)
            while y <= maxy:
                x = minx + (step / 2)
                while x <= maxx:
                    # 1. Normalize position [0.0, 1.0] across the bounding box
                    nx = (x - minx) / width
                    ny = (y - miny) / height

                    # 2. Calculate the morph phase
                    # Projecting the 2D coordinates onto a diagonal vector to create a propagating wave
                    t = nx * math.cos(math.pi / 4) + ny * math.sin(math.pi / 4)
                    
                    # Generate the underlying signal wave
                    phase = math.sin(t * math.pi * 2 * morph_cycles)

                    # Normalize the phase to [0.0, 1.0] for parameter mapping
                    norm_phase = (phase + 1) / 2.0

                    # 3. Apply the morphing parameters driven by the signal:
                    # Vertices: 3 (triangle) morphing up to 8 (octagon)
                    sides = int(3 + (5 * norm_phase))

                    # Scale: Pulse the amplitude between 30% and 90% of cell capacity
                    radius = (step / 2.0) * (0.3 + (0.6 * norm_phase))

                    # Rotation: Twist the geometry based on the wave phase
                    rotation_rads = norm_phase * math.pi

                    # 4. Construct the n-sided polygon for this grid cell
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

        return _apply_pattern_to_shape(shape, angle, morph_generator, spacing=spacing)
