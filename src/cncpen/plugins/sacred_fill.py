import math

from shapely.geometry import Point

from cncpen.fills import _apply_pattern_to_shape
from cncpen.fills import register_fill


@register_fill("sacred")
def generate_sacred_geometry_fill(shape, spacing, angle=0.0, **kwargs):
    """Generates a Flower of Life (overlapping circles) sacred geometry fill."""

    def sacred_generator(p, spacing):
        minx, miny, maxx, maxy = p.bounds
        radius = max(spacing, 0.1)
        dx = radius
        dy = radius * math.sqrt(3) / 2.0

        # Pad the bounding box
        minx -= radius
        maxx += radius
        miny -= radius
        maxy += radius

        circles = []
        row = 0
        y = miny

        while y <= maxy:
            x_offset = (radius / 2.0) if (row % 2 != 0) else 0.0
            x = minx + x_offset
            while x <= maxx:
                circle_outline = Point(x, y).buffer(radius,
                                                    resolution=32).exterior
                circles.append(circle_outline)
                x += dx
            y += dy
            row += 1

        return circles

    return _apply_pattern_to_shape(shape,
                                   angle,
                                   sacred_generator,
                                   spacing=spacing)
