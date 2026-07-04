import argparse
from PIL import Image
from shapely.geometry import LineString
from cncpen.fills import register_fill

@register_fill("photo_hatch")
class PhotoHatchFill:
    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--image", required=True, help="Path to the source photograph")
        parser.add_argument("--cell-size", type=float, default=2.0, help="Size of the hatching grid cells")

    def generate(self, shape, image: str, cell_size: float, **kwargs) -> list[LineString]:
        img = Image.open(image).convert("L")
        minx, miny, maxx, maxy = shape.bounds
        
        output_paths = []
        
        x = minx
        while x < maxx:
            y = miny
            while y < maxy:
                # Map cell center to pixel
                cx, cy = x + (cell_size / 2), y + (cell_size / 2)
                px = int(((cx - minx) / (maxx - minx)) * (img.width - 1))
                py = int((1.0 - ((cy - miny) / (maxy - miny))) * (img.height - 1))
                
                # Clamp coordinates just in case
                px = max(0, min(px, img.width - 1))
                py = max(0, min(py, img.height - 1))
                
                darkness = (255 - img.getpixel((px, py))) / 255.0
                
                # Add diagonal 1 if medium dark
                if darkness > 0.3:
                    output_paths.append(LineString([(x, y), (x + cell_size, y + cell_size)]))
                
                # Add cross diagonal if very dark
                if darkness > 0.7:
                    output_paths.append(LineString([(x, y + cell_size), (x + cell_size, y)]))
                    
                y += cell_size
            x += cell_size
            
        return output_paths
