from dataclasses import dataclass
from typing import Any, List, Protocol

from PIL import Image
from shapely.geometry import LineString
from shapely.geometry import Point
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

FILL_REGISTRY = {}
MODIFICATION_REGISTRY = {}


def register_fill(name):

    def decorator(cls):
        FILL_REGISTRY[name] = cls
        return cls

    return decorator


def register_modification(name):

    def decorator(cls):
        MODIFICATION_REGISTRY[name] = cls
        return cls

    return decorator


class ImageSampler:

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


@dataclass
class RenderContext:
    """Holds read-only state for the current fill operation."""
    config: dict
    boundary: Polygon
    centroid: Point
    max_r: float

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return self.boundary.bounds


class FillPattern(Protocol):

    def generate(self, shape: BaseGeometry,
                 context: RenderContext) -> List[LineString]:
        ...


class PathModification(Protocol):

    def is_active(self, config: dict) -> bool:
        ...

    def apply(self, lines: List[LineString],
              context: RenderContext) -> List[LineString]:
        ...
