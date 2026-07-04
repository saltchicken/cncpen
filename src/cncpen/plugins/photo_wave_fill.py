import math
import argparse
from PIL import Image
from shapely.geometry import LineString
from cncpen.fills import register_fill

@register_fill("photo_wave")
class PhotoWaveFill:
    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--image", required=True, help="Path to the source photograph")
        parser.add_argument("--lines", type=int, default=80, help="Number of horizontal wave lines")
        parser.add_argument("--amp", type=float, default=2.0, help="Maximum wave amplitude multiplier")

    def generate(self, shape, image: str, lines: int, amp: float, **kwargs) -> list[LineString]:
        img = Image.open(image).convert("L")
        minx, miny, maxx, maxy = shape.bounds
        width, height = maxx - minx, maxy - miny
        
        row_spacing = height / lines
        output_paths = []
        
        for r in range(lines):
            y_base = miny + (r * row_spacing)
            coords = []
            
            # Sample along the X axis
            steps = int(width * 5)  # High resolution for smooth curves
            for s in range(steps):
                x = minx + (s * (width / steps))
                
                # Map CNC coordinates to Image pixels (invert Y)
                px = int((s / steps) * (img.width - 1))
                py = int((1.0 - (r / lines)) * (img.height - 1))
                
                # Calculate darkness (0.0 = white, 1.0 = black)
                darkness = (255 - img.getpixel((px, py))) / 255.0
                
                # Modulate wave
                y_offset = math.sin(x * 3.0) * (row_spacing * amp * 0.5) * darkness
                coords.append((x, y_base + y_offset))
                
            output_paths.append(LineString(coords))
            
        return output_paths
