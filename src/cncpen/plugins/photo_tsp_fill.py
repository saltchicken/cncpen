import random
import math
import argparse
from PIL import Image
from shapely.geometry import LineString
from cncpen.fills import register_fill

@register_fill("photo_tsp")
class PhotoTSPFill:
    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--image", required=True, help="Path to the source photograph")
        parser.add_argument("--nodes", type=int, default=2000, help="Number of nodes to connect")

    def generate(self, shape, image: str, nodes: int, **kwargs) -> list[LineString]:
        img = Image.open(image).convert("L")
        minx, miny, maxx, maxy = shape.bounds
        width, height = maxx - minx, maxy - miny
        
        # 1. Generate weighted random points (same logic as stippling)
        points = []
        attempts = 0
        while len(points) < nodes and attempts < (nodes * 10):
            attempts += 1
            rx, ry = random.uniform(0, width), random.uniform(0, height)
            px = int((rx / width) * (img.width - 1))
            py = int((1.0 - (ry / height)) * (img.height - 1))
            
            if random.random() < ((255 - img.getpixel((px, py))) / 255.0):
                points.append((minx + rx, miny + ry))
                
        if not points:
            return []

        # 2. Greedy Nearest Neighbor TSP to form a single continuous line
        current = points.pop(0)
        route = [current]
        
        while points:
            # Find closest point
            best_idx = -1
            best_dist = float('inf')
            
            for i, p in enumerate(points):
                dist = math.hypot(current[0] - p[0], current[1] - p[1])
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i
                    
            current = points.pop(best_idx)
            route.append(current)
            
        return [LineString(route)]
