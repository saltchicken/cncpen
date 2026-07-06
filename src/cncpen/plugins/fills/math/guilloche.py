import math
from typing import List

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from cncpen import register_fill
from cncpen import RenderContext


@register_fill("guilloche")
class GuillocheFill:
    def generate(self, shape: BaseGeometry, context: RenderContext) -> List[LineString]:
        params = context.config.params
        
        # Core roulette curve parameters
        # R: Radius of the fixed circle
        # r: Radius of the rolling circle (negative for hypotrochoid, positive for epitrochoid)
        # p: Distance from the center of the rolling circle to the pen tip
        R = params.get('major_radius', 50.0)
        r = params.get('minor_radius', -15.0)
        p = params.get('pen_offset', 25.0)
        
        # Rendering parameters
        revolutions = params.get('revolutions', 10)
        resolution = params.get('resolution', 0.05)  # radians per step
        
        # Center the pattern on the bounding geometry's centroid
        cx, cy = context.centroid.x, context.centroid.y
        
        points = []
        max_theta = revolutions * 2 * math.pi
        theta = 0.0
        
        # Pre-calculate the ratio to save operations in the loop
        if r == 0:
            r = 0.0001 # Prevent division by zero
        ratio = (R + r) / r

        while theta <= max_theta:
            # Parametric equations for the roulette curve
            x = cx + (R + r) * math.cos(theta) + p * math.cos(ratio * theta)
            y = cy + (R + r) * math.sin(theta) + p * math.sin(ratio * theta)
            
            points.append((x, y))
            theta += resolution
            
        # Ensure the loop closes cleanly if it completes a perfect cycle
        if points:
            points.append((
                cx + (R + r) * math.cos(max_theta) + p * math.cos(ratio * max_theta),
                cy + (R + r) * math.sin(max_theta) + p * math.sin(ratio * max_theta)
            ))

        if len(points) > 1:
            return [LineString(points)]
        return []
