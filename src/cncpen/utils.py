import ezdxf
from ezdxf.path import make_path
import sys
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge

def extract_dxf_paths(filepath, flatten_distance=0.1, simplify_tolerance=0.0):
    """
    Reads a DXF file, flattens entities, and stitches disconnected 
    segments together to heal poor SVG-to-DXF conversions.
    """
    try:
        doc = ezdxf.readfile(filepath)
    except Exception as e:
        print(f"Error reading DXF file '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)

    msp = doc.modelspace()
    raw_lines = []

    supported_types = {
        'LINE', 'LWPOLYLINE', 'POLYLINE', 'CIRCLE', 'ARC', 'ELLIPSE', 'SPLINE'
    }

    # 1. Extract everything as raw Shapely LineStrings
    for entity in msp:
        if entity.dxftype() in supported_types:
            try:
                p = make_path(entity)
                vertices = list(p.flattening(flatten_distance))

                if len(vertices) > 1:
                    raw_lines.append(LineString([(v.x, v.y) for v in vertices]))
            except Exception as e:
                print(
                    f"Warning: could not process {entity.dxftype()} entity: {e}",
                    file=sys.stderr)

    if not raw_lines:
        return []

    # 2. Stitch touching line segments together
    merged_geometry = linemerge(raw_lines)

    # NEW: Apply simplification if a tolerance is provided
    if simplify_tolerance > 0:
        merged_geometry = merged_geometry.simplify(simplify_tolerance, preserve_topology=True)

    paths = []
    
    # 3. Format back into point lists for the CNC pen
    if isinstance(merged_geometry, LineString):
        paths.append(list(merged_geometry.coords))
    elif isinstance(merged_geometry, MultiLineString):
        for line in merged_geometry.geoms:
            paths.append(list(line.coords))

    return paths
