import argparse
from functools import partial
import importlib
import math
from pathlib import Path
import sys
from typing import Any, List, Protocol

from PIL import Image
from shapely import affinity
from shapely.geometry import LineString
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from .filters import apply_clipping
from .filters import apply_fisheye
from .filters import apply_image_mask
from .filters import apply_roughening
from .filters import apply_transform
from .pipeline import PenStroke
from .pipeline import PipelineHistory

FILL_REGISTRY = {}


class ImageSampler:
    """Maps physical CNC coordinates to image pixels and returns darkness values."""

    def __init__(self, image_path: str, bounds: tuple):
        self.img = Image.open(image_path).convert("L")
        self.minx, self.miny, self.maxx, self.maxy = bounds
        self.width = self.maxx - self.minx
        self.height = self.maxy - self.miny

    def get_darkness(self, x: float, y: float) -> float:
        if self.width == 0 or self.height == 0:
            return 0.0
        px = max(
            0,
            min(int(((x - self.minx) / self.width) * (self.img.width - 1)),
                self.img.width - 1))
        py = max(
            0,
            min(
                int((1.0 - ((y - self.miny) / self.height)) *
                    (self.img.height - 1)), self.img.height - 1))
        return (255 - self.img.getpixel((px, py))) / 255.0


class FillPattern(Protocol):

    @classmethod
    def setup_cli(cls, parser: argparse.ArgumentParser) -> None:
        ...

    def generate(self, shape: BaseGeometry, **kwargs: Any) -> List[LineString]:
        ...


def register_fill(name):

    def decorator(cls):
        FILL_REGISTRY[name] = cls
        return cls

    return decorator


def _ensure_geom(shape):
    poly = shape if isinstance(shape, BaseGeometry) else (
        Polygon() if len(shape) < 4 else Polygon(shape))
    return poly if poly.is_valid and poly.area > 0 else poly.buffer(0)


def generate_pipeline(filler,
                      shape,
                      angle=0.0,
                      fisheye=0.0,
                      image=None,
                      simplify=0.0,
                      **kwargs) -> List[PenStroke]:
    """The FP Orchestrator: Wires the pure filters and executes the timeline."""
    poly = _ensure_geom(shape)
    if poly.is_empty or poly.area == 0:
        return []

    centroid = poly.centroid
    working_poly = affinity.rotate(poly, -angle,
                                   origin=centroid) if angle != 0.0 else poly

    global_minx, global_miny, global_maxx, global_maxy = working_poly.bounds
    max_r = math.hypot(global_maxx - global_minx,
                       global_maxy - global_miny) / 2.0
    sampler = ImageSampler(image, working_poly.bounds) if image else None

    # Gather raw output from the plugin
    all_raw_lines = []
    polygons = [working_poly] if working_poly.geom_type == 'Polygon' else list(
        working_poly.geoms)
    for p in polygons:
        all_raw_lines.extend(filler.generate(p, sampler=sampler, **kwargs))

    # Convert to FP immutable wrappers
    initial_strokes = [
        PenStroke(geometry=line) for line in all_raw_lines if not line.is_empty
    ]

    # Initialize the time machine
    state_manager = PipelineHistory(initial_strokes)

    # 1. Image Masking
    if sampler and not getattr(filler, 'handles_image_natively', False):
        state_manager.apply_filter(
            partial(apply_image_mask,
                    sampler=sampler,
                    threshold=kwargs.get('threshold', 0.1)))

    # 2. Roughening
    if kwargs.get('roughen_amp', 0.0) > 0.0:
        state_manager.apply_filter(
            partial(apply_roughening,
                    amplitude=kwargs.get('roughen_amp'),
                    step=kwargs.get('roughen_step', 1.0)))

    # 3. Fisheye Distortion
    if fisheye != 0.0:
        state_manager.apply_filter(
            partial(apply_fisheye,
                    factor=fisheye,
                    centroid=centroid,
                    max_r=max_r))

    # 4. Final Clip and Transform Cleanup
    for p in polygons:
        state_manager.apply_filter(partial(apply_clipping, boundary=p))
        state_manager.apply_filter(
            partial(apply_transform,
                    angle=angle,
                    origin=centroid,
                    simplify_tol=simplify))

    return state_manager.get_current_state()


def load_plugins():
    plugins_dir = Path(__file__).parent / "plugins"
    if not plugins_dir.exists():
        return
    for file_path in plugins_dir.rglob("*.py"):
        if file_path.name == "__init__.py":
            continue
        relative_path = file_path.relative_to(plugins_dir)
        module_name = f"cncpen.plugins.{'.'.join(relative_path.with_suffix('').parts)}"
        try:
            importlib.import_module(module_name)
        except Exception as e:
            print(f"Warning: Failed to load plugin '{relative_path}': {e}",
                  file=sys.stderr)
