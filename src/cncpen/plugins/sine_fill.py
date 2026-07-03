import math
from shapely.geometry import LineString
from cncpen.fills import register_fill, _apply_pattern_to_shape

@register_fill("sine")
def generate_sinewave_fill(shape, spacing, amplitude=1.0, wavelength=5.0, angle=0.0, **kwargs):
    """Generates back-and-forth sine wave fill paths for a closed polygon."""
    
    def sinewave_generator(p, spacing, amplitude, wavelength):
        minx, miny, maxx, maxy = p.bounds
        y = miny + spacing
        lines = []
        left_to_right = True
        resolution = 0.2
        
        while y <= maxy + amplitude:
            x_start, x_end = minx - 1, maxx + 1
            wave_points = []
            num_steps = int(math.ceil((x_end - x_start) / resolution))
            
            for i in range(num_steps + 1):
                cx = x_start + i * resolution
                cy = y + amplitude * math.sin(2 * math.pi * cx / wavelength)
                wave_points.append((cx, cy))
                
            if not left_to_right:
                wave_points.reverse()
                
            lines.append(LineString(wave_points))
            y += spacing
            left_to_right = not left_to_right
            
        return lines

    return _apply_pattern_to_shape(shape, angle, sinewave_generator, 
                                   spacing=spacing, amplitude=amplitude, wavelength=wavelength)
