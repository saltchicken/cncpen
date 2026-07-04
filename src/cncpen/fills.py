import importlib
import math
import sys
import argparse
from pathlib import Path
from typing import Protocol, List, Any

from shapely import affinity
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from PIL import Image

FILL_REGISTRY = {}


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


def _apply_image_mask(lines: List[LineString], sampler: ImageSampler, threshold: float) -> List[LineString]:
    """Breaks continuous lines into segments based on image darkness."""
    step_res = 1.0  # 1mm sampling intervals
    masked_lines = []
    
    for line in lines:
        length = line.length
        if length == 0:
            continue
            
        steps = max(2, int(math.ceil(length / step_res)))
        current_segment = []
        
        for i in range(steps + 1):
            pt = line.interpolate(i / steps, normalized=True)
            cx, cy = pt.x, pt.y
            
            if sampler.get_darkness(cx, cy) > threshold:
                current_segment.append((cx, cy))
            else:
                if len(current_segment) > 1:
                    masked_lines.append(LineString(current_segment))
                current_segment = []
                
        if len(current_segment) > 1:
            masked_lines.append(LineString(current_segment))
            
    return masked_lines


def generate_pipeline(filler, shape, angle=0.0, fisheye=0.0, image=None, simplify=0.0, **kwargs):
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

    sampler = ImageSampler(image, working_poly.bounds) if image else None

    all_fill_paths = []
    polygons = [working_poly] if working_poly.geom_type == 'Polygon' else list(working_poly.geoms)

    for p in polygons:
        # 2. Plugin generates raw lines mapping only to 'p'
        raw_lines = filler.generate(p, sampler=sampler, **kwargs)
        
        if not raw_lines:
            continue

        # 2.5 Apply generic image masking ONLY if the plugin doesn't handle it natively
        if sampler and not getattr(filler, 'handles_image_natively', False):
            threshold = kwargs.get('threshold', 0.1)
            raw_lines = _apply_image_mask(raw_lines, sampler, threshold)

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

        # 4. Clip to boundary, rotate back, and optionally simplify
        for line in raw_lines:
            intersection = p.intersection(line)
            clipped_lines = _extract_lines(intersection)
            
            for clipped in clipped_lines:
                if angle != 0.0:
                    clipped = affinity.rotate(clipped, angle, origin=centroid)
                
                if simplify > 0.0:
                    clipped = clipped.simplify(simplify, preserve_topology=False)

                all_fill_paths.append(list(clipped.coords))

    return all_fill_paths


def load_plugins():
    """Dynamically loads all modules in the plugins directory and subdirectories."""
    plugins_dir = Path(__file__).parent / "plugins"

    if not plugins_dir.exists():
        return

    # 1. Use rglob (recursive glob) to search all subfolders
    for file_path in plugins_dir.rglob("*.py"):
        if file_path.name == "__init__.py":
            continue

        # 2. Calculate the relative path to properly format the module import string
        relative_path = file_path.relative_to(plugins_dir)
        
        # e.g., from "math_patterns/spiral.py" -> ["math_patterns", "spiral"]
        module_parts = list(relative_path.parts[:-1]) + [relative_path.stem]
        module_path = ".".join(module_parts)
        
        module_name = f"cncpen.plugins.{module_path}"
        
        try:
            importlib.import_module(module_name)
        except Exception as e:
            print(f"Warning: Failed to load plugin '{relative_path}': {e}", file=sys.stderr)
