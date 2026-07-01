import argparse
import sys
import math
import ezdxf
from ezdxf.path import make_path
from dataclasses import dataclass
from gscrib import GCodeBuilder
from shapely.geometry import Polygon, LineString

@dataclass
class PenConfig:
    clearance_z: float = 5.0
    rapid_z: float = 1.0
    feed_rate: float = 400.0
    down_z: float = -1.0

class PenTool():
    def __init__(self, config: PenConfig, output_filename="output.nc"):
        self.g = GCodeBuilder(output=output_filename)
        self.config = config

    def __enter__(self):
        self._build_preamble()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tool_off()
        self._build_postamble()
        self.g.flush()
    
    def _build_preamble(self):
        self.g.set_plane('xy')
        self.g.set_distance_mode('absolute')
        self.g.set_length_units('mm')
        self.g.write("G54") # Work Coordinate System Home

    def _build_postamble(self):
        """Writes the required final G-code commands."""
        self.g.write("M5")
        self.g.write("G17 G90")
        self.g.write("M2")

    def move_to(self, x, y):
        self.g.rapid(z=self.config.clearance_z)
        self.g.rapid(x=x, y=y)

    def tool_on(self):
        # NOTE: Z axis applies pressure
        self.g.move(z=self.config.down_z)

    def tool_off(self):
        # NOTE: Rapid lift to clearance_z to move pen tip away from stock
        self.g.rapid(z=self.config.clearance_z)

    def draw_path(self, points):
        """Draws a series of points."""
        if not points:
            return
        self.move_to(*points[0])
        self.tool_on()
        for x, y in points[1:]:
            self.g.move(x=x, y=y, f=self.config.feed_rate)
        self.tool_off()


def generate_zigzag_fill(points, spacing):
    """
    Generates back-and-forth (zig-zag) fill paths for a closed polygon.
    """
    if len(points) < 4:
        return []
        
    poly = Polygon(points)
    
    # Attempt to buffer out slight self-intersections (e.g. figure-8 loops)
    if not poly.is_valid or poly.area == 0:
        poly = poly.buffer(0)
        if poly.area == 0:
            return []

    # Buffering can result in a MultiPolygon
    polygons = [poly] if poly.geom_type == 'Polygon' else list(poly.geoms)
    all_fill_paths = []
    
    for p in polygons:
        minx, miny, maxx, maxy = p.bounds
        y = miny + spacing
        
        left_to_right = True
        
        while y <= maxy:
            # Create a scanline that completely covers the bounding box horizontally
            scanline = LineString([(minx - 1, y), (maxx + 1, y)])
            intersection = p.intersection(scanline)
            
            if intersection.is_empty:
                y += spacing
                continue
            
            # Extract standard LineStrings from the intersection result
            lines = []
            if intersection.geom_type == 'LineString':
                lines.append(intersection)
            elif intersection.geom_type == 'MultiLineString':
                lines.extend(list(intersection.geoms))
            elif intersection.geom_type == 'GeometryCollection':
                for geom in intersection.geoms:
                    if geom.geom_type == 'LineString':
                        lines.append(geom)

            if not lines:
                y += spacing
                continue
            
            # Sort the cut segments left-to-right to maintain logical travel moves
            lines.sort(key=lambda l: l.coords[0][0])
            
            # If we are travelling right-to-left, flip the segments and their contents
            if not left_to_right:
                lines.reverse()
                
            for line in lines:
                coords = list(line.coords)
                if not left_to_right:
                    coords.reverse()
                all_fill_paths.append(coords)
            
            # Flip direction for the next horizontal line
            left_to_right = not left_to_right
            y += spacing

    return all_fill_paths


def extract_dxf_paths(filepath, flatten_distance=0.1):
    """
    Reads a DXF file and converts geometric entities into a list of point lists.
    """
    try:
        doc = ezdxf.readfile(filepath)
    except Exception as e:
        print(f"Error reading DXF file '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)

    msp = doc.modelspace()
    paths = []

    supported_types = {'LINE', 'LWPOLYLINE', 'POLYLINE', 'CIRCLE', 'ARC', 'ELLIPSE', 'SPLINE'}

    for entity in msp:
        if entity.dxftype() in supported_types:
            try:
                p = make_path(entity)
                vertices = list(p.flattening(flatten_distance))
                
                if vertices:
                    paths.append([(v.x, v.y) for v in vertices])
            except Exception as e:
                print(f"Warning: could not process {entity.dxftype()} entity: {e}", file=sys.stderr)

    return paths


def main():
    parser = argparse.ArgumentParser(description="Generate CNC G-code from a DXF file using a pen tool.")
    parser.add_argument("dxf_file", help="Path to the input DXF file")
    parser.add_argument("-o", "--output", default="output.nc", help="Output G-code filename (default: output.nc)")
    parser.add_argument("--feed", type=float, default=400.0, help="Drawing feed rate (default: 400.0)")
    parser.add_argument("--fill", action="store_true", help="Enable zig-zag fill for closed shapes")
    parser.add_argument("--spacing", type=float, default=1.0, help="Distance between fill lines (default: 1.0)")
    
    args = parser.parse_args()

    print(f"Reading geometry from {args.dxf_file}...")
    paths_to_draw = extract_dxf_paths(args.dxf_file)
    print(f"Extracted {len(paths_to_draw)} draw operations.")

    if not paths_to_draw:
        print("No drawable paths found. Exiting.")
        sys.exit(0)

    config = PenConfig(feed_rate=args.feed)
    
    with PenTool(config, output_filename=args.output) as pen:
        for pts in paths_to_draw:
            # 1. Draw the outer boundary / standard lines
            pen.draw_path(pts)
            
            # 2. Draw the infill if enabled, and if the path is closed
            if args.fill and len(pts) > 2:
                dx = pts[0][0] - pts[-1][0]
                dy = pts[0][1] - pts[-1][1]
                
                # Check if path is closed (start and end points overlap)
                if math.hypot(dx, dy) < 0.01:
                    fill_paths = generate_zigzag_fill(pts, args.spacing)
                    for f_pts in fill_paths:
                        pen.draw_path(f_pts)
            
    print(f"G-code successfully saved to {args.output}")

if __name__ == "__main__":
    main()
