import random
import argparse
from PIL import Image
from shapely.geometry import LineString
from cncpen.fills import register_fill

@register_fill("photo_stipple")
class PhotoStippleFill:
    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--image", required=True, help="Path to the source photograph")
        parser.add_argument("--dots", type=int, default=5000, help="Target number of stipple dots")

    def generate(self, shape, image: str, dots: int, **kwargs) -> list[LineString]:
        img = Image.open(image).convert("L")
        minx, miny, maxx, maxy = shape.bounds
        width, height = maxx - minx, maxy - miny
        
        output_paths = []
        attempts = 0
        max_attempts = dots * 10 
        
        while len(output_paths) < dots and attempts < max_attempts:
            attempts += 1
            
            # Pick a random physical coordinate
            rx = random.uniform(0, width)
            ry = random.uniform(0, height)
            
            # Map to pixel
            px = int((rx / width) * (img.width - 1))
            py = int((1.0 - (ry / height)) * (img.height - 1))
            
            # Probability of placing a dot equals pixel darkness
            darkness = (255 - img.getpixel((px, py))) / 255.0
            
            if random.random() < darkness:
                actual_x = minx + rx
                actual_y = miny + ry
                # Create a tiny 0.1mm line segment to force a pen dot
                output_paths.append(LineString([(actual_x, actual_y), (actual_x + 0.1, actual_y)]))
                
        return output_paths
