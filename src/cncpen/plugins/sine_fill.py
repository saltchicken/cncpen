import argparse
import math
from typing import List, Any

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen.fills import _apply_pattern_to_shape
from cncpen.fills import register_fill


@register_fill("sine")
class SineFill:
    """Generates back-and-forth sine wave fill paths for a closed polygon."""
    
    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--amplitude", type=float, default=1.0,
                            help="Amplitude for the sine wave pattern (default: 1.0)")
        parser.add_argument("--wavelength", type=float, default=5.0,
                            help="Wavelength for the sine wave pattern (default: 5.0)")

    def generate(self, shape: BaseGeometry, spacing: float, amplitude: float = 1.0, 
                 wavelength: float = 5.0, angle: float = 0.0, **kwargs: Any) -> List[List[tuple[float, float]]]:
        def sinewave_generator(p, spacing, amplitude, wavelength):
            minx, miny, maxx, maxy = p.bounds
            y = miny + spacing
            lines = []
            left_to_right = True
            resolution = 0.2

            while y <= maxy + amplitude:
                x_start, x_end = minx - 1, maxx + 1
                wave_points = []
                num_steps = int(math.ceil((x_end - x_start) / resolution))

                for i in range(num_steps + 1):
                    cx = x_start + i * resolution
                    cy = y + amplitude * math.sin(2 * math.pi * cx / wavelength)
                    wave_points.append((cx, cy))

                if not left_to_right:
                    wave_points.reverse()

                lines.append(LineString(wave_points))
                y += spacing
                left_to_right = not left_to_right

            return lines

        return _apply_pattern_to_shape(
            shape, angle, sinewave_generator, spacing=spacing, 
            amplitude=amplitude, wavelength=wavelength)
