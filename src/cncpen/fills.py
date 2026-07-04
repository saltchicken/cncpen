import importlib
import math
import sys
import argparse
from pathlib import Path
from typing import Protocol, List, Any

from shapely import affinity
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry

# --- REGISTRY SYSTEM ---
FILL_REGISTRY = {}

from PIL import Image

class ImageSampler:
    """Maps physical CNC coordinates to image pixels and returns darkness values."""
    def __init__(self, image_path: str, bounds: tuple):
        self.img = Image.open(image_path).convert("L")
        self.minx, self.miny, self.maxx, self.maxy = bounds
        self.width = self.maxx - self.minx
        self.height = self.maxy - self.miny

    def get_darkness(self, x: float, y: float) -> float:
        """Returns a value from 0.0 (pure white) to 1.0 (pure black)."""
        if self.width == 0 or self.height == 0:
            return 0.0
            
        # Map physical coordinates to pixel coordinates
        px = int(((x - self.minx) / self.width) * (self.img.width - 1))
        py = int((1.0 - ((y - self.miny) / self.height)) * (self.img.height - 1))
        
        # Clamp to bounds to prevent out-of-range errors during edge sampling
        px = max(0, min(px, self.img.width - 1))
        py = max(0, min(py, self.img.height - 1))
        
        return (255 - self.img.getpixel((px, py))) / 255.0

class FillPattern(Protocol):
    """Protocol defining the interface for all fill plugins."""
    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        """Register plugin-specific command line arguments."""
        ...

    def generate(self, shape: BaseGeometry, **kwargs: Any) -> List[LineString]:
        """Generate a list of raw, unclipped LineStrings mapping over the shape bounds."""
        ...


def register_fill(name):
    """Decorator to automatically register a fill pattern class."""
    def decorator(cls):
        FILL_REGISTRY[name] = cls
        return cls
    return decorator


def _ensure_geom(shape):
    """Helper to handle either a raw list of points or a Shapely geometry."""
    if isinstance(shape, BaseGeometry):
        poly = shape
    elif len(shape) < 4:
        poly = Polygon()
    else:
        poly = Polygon(shape)

    if not poly.is_valid or poly.area == 0:
        poly = poly.buffer(0)
        
    return poly


def _extract_lines(geometry):
    """Flattens diverse Shapely geometries into a list of LineStrings."""
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'LineString':
        return [geometry]
    elif geometry.geom_type == 'MultiLineString':
        return list(geometry.geoms)
    elif geometry.geom_type == 'GeometryCollection':
        return [g for g in geometry.geoms if g.geom_type == 'LineString']
    return []


def generate_pipeline(filler, shape, angle=0.0, fisheye=0.0, **kwargs):
    """
    The Central Pipeline: Takes raw generated lines from a plugin and applies 
    global transformations, distortions, and boundary clipping.
    """
    poly = _ensure_geom(shape)
    if poly.is_empty or poly.area == 0:
        return []

    centroid = poly.centroid
    
    # 1. Rotate the shape so the plugin works on a flattened canvas
    working_poly = poly
    if angle != 0.0:
        working_poly = affinity.rotate(poly, -angle, origin=centroid)

    global_minx, global_miny, global_maxx, global_maxy = working_poly.bounds
    global_max_r = math.hypot(global_maxx - global_minx, global_maxy - global_miny) / 2.0

    sampler = None
    if kwargs.get("image"):
        sampler = ImageSampler(kwargs["image"], working_poly.bounds)
        kwargs["sampler"] = sampler  # Inject it into kwargs for the plugin

    all_fill_paths = []
    polygons = [working_poly] if working_poly.geom_type == 'Polygon' else list(working_poly.geoms)

    for p in polygons:
        # 2. Plugin generates raw lines mapping only to 'p'
        raw_lines = filler.generate(p, **kwargs)
        if not raw_lines:
            continue

        # 3. Apply Fisheye / Radial Distortion
        if fisheye != 0.0 and global_max_r > 0:
            distorted_lines = []
            for line in raw_lines:
                length = line.length
                if length > 0:
                    num_segments = max(2, int(math.ceil(length / 0.5)))
                    points = [line.interpolate(i / num_segments, normalized=True).coords[0] for i in range(num_segments + 1)]
                    warped_coords = []
                    for px, py in points:
                        dx, dy = px - centroid.x, py - centroid.y
                        r = math.hypot(dx, dy)
                        factor = 1.0 + fisheye * ((r / global_max_r) ** 2) if r > 0 else 1.0
                        warped_coords.append((centroid.x + dx * factor, centroid.y + dy * factor))
                    distorted_lines.append(LineString(warped_coords))
            raw_lines = distorted_lines

        # 4. Clip to boundary and rotate back
        for line in raw_lines:
            intersection = p.intersection(line)
            clipped_lines = _extract_lines(intersection)
            
            for clipped in clipped_lines:
                if angle != 0.0:
                    clipped = affinity.rotate(clipped, angle, origin=centroid)
                all_fill_paths.append(list(clipped.coords))

    return all_fill_paths


@register_fill("zigzag")
class ZigZagFill:
    """Generates back-and-forth hatch paths, optionally masked out by image brightness."""
    
    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        pass 

    def generate(self, shape: BaseGeometry, spacing: float, sampler=None, **kwargs: Any) -> List[LineString]:
        minx, miny, maxx, maxy = shape.bounds
        y = miny + spacing
        lines = []
        left_to_right = True
        step_res = 1.0 # 1mm sampling intervals for the line breaks

        while y <= maxy:
            x_start, x_end = (minx - 1, maxx + 1) if left_to_right else (maxx + 1, minx - 1)
            
            if not sampler:
                # Standard Mode: Just draw a clean continuous line across the canvas
                lines.append(LineString([(x_start, y), (x_end, y)]))
            else:
                # Photo Mode: Break the line up, only dropping the pen where it's dark
                current_x = x_start
                direction = 1.0 if left_to_right else -1.0
                total_dist = abs(x_end - x_start)
                steps = int(math.ceil(total_dist / step_res))
                
                segment_points = []
                for i in range(steps + 1):
                    cx = x_start + (i * step_res * direction)
                    
                    # Keep lines only if the area isn't close to pure white
                    if sampler.get_darkness(cx, y) > 0.1:
                        segment_points.append((cx, y))
                    else:
                        # Break the path if we hit a white area to lift the pen
                        if len(segment_points) > 1:
                            lines.append(LineString(segment_points))
                        segment_points = []
                        
                if len(segment_points) > 1:
                    lines.append(LineString(segment_points))

            y += spacing
            left_to_right = not left_to_right

        return lines


@register_fill("concentric")
class ConcentricFill:
    """Generates concentric (inset) fill paths."""
    
    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--ring-simplify", type=float, default=0.2, 
                            help="Simplification tolerance specific to inner concentric rings (default: 0.2)")

    def generate(self, shape: BaseGeometry, spacing: float, ring_simplify: float = 0.2, **kwargs: Any) -> List[LineString]:
        lines = []
        current_geom = shape.buffer(-spacing).simplify(ring_simplify, preserve_topology=False)

        while not current_geom.is_empty and current_geom.area > 0:
            polygons = [current_geom] if current_geom.geom_type == 'Polygon' else list(current_geom.geoms)
            for p in polygons:
                if p.exterior:
                    lines.append(LineString(p.exterior.coords))
                for interior in p.interiors:
                    lines.append(LineString(interior.coords))
            current_geom = current_geom.buffer(-spacing).simplify(ring_simplify, preserve_topology=False)

        return lines


def load_plugins():
    """Dynamically loads all modules in the plugins directory."""
    plugins_dir = Path(__file__).parent / "plugins"

    if not plugins_dir.exists():
        return

    for file_path in plugins_dir.glob("*.py"):
        if file_path.name == "__init__.py":
            continue

        module_name = f"cncpen.plugins.{file_path.stem}"
        try:
            importlib.import_module(module_name)
        except Exception as e:
            print(f"Warning: Failed to load plugin '{file_path.name}': {e}", file=sys.stderr)
