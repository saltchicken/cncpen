from shapely import affinity
from shapely.geometry import LineString
from shapely.geometry import Polygon


def generate_zigzag_fill(points, spacing, angle=0.0):
    """
    Generates back-and-forth (zig-zag) fill paths for a closed polygon.
    """
    if len(points) < 4:
        return []

    poly = Polygon(points)

    if not poly.is_valid or poly.area == 0:
        poly = poly.buffer(0)
        if poly.area == 0:
            return []

    centroid = poly.centroid

    if angle != 0.0:
        poly = affinity.rotate(poly, -angle, origin=centroid)

    polygons = [poly] if poly.geom_type == 'Polygon' else list(poly.geoms)
    all_fill_paths = []

    for p in polygons:
        minx, miny, maxx, maxy = p.bounds
        y = miny + spacing
        left_to_right = True

        while y <= maxy:
            scanline = LineString([(minx - 1, y), (maxx + 1, y)])
            intersection = p.intersection(scanline)

            if intersection.is_empty:
                y += spacing
                continue

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

            lines.sort(key=lambda l: l.coords[0][0])
            if not left_to_right:
                lines.reverse()

            for line in lines:
                if angle != 0.0:
                    line = affinity.rotate(line, angle, origin=centroid)

                coords = list(line.coords)
                if not left_to_right:
                    coords.reverse()
                all_fill_paths.append(coords)

            left_to_right = not left_to_right
            y += spacing

    return all_fill_paths


def generate_sinewave_fill(points,
                           spacing,
                           amplitude=1.0,
                           wavelength=5.0,
                           angle=0.0):
    """
    Generates back-and-forth sine wave fill paths for a closed polygon.
    """
    if len(points) < 4:
        return []

    poly = Polygon(points)

    if not poly.is_valid or poly.area == 0:
        poly = poly.buffer(0)
        if poly.area == 0:
            return []

    centroid = poly.centroid

    if angle != 0.0:
        poly = affinity.rotate(poly, -angle, origin=centroid)

    polygons = [poly] if poly.geom_type == 'Polygon' else list(poly.geoms)
    all_fill_paths = []

    # Resolution (mm) defines how many segments make up the curve.
    # Smaller is smoother, but creates more G-code lines.
    resolution = 0.2

    for p in polygons:
        minx, miny, maxx, maxy = p.bounds
        # Pad the Y loop so waves near the top border don't get missed due to amplitude dipping
        y = miny + spacing
        left_to_right = True

        while y <= maxy + amplitude:
            x_start = minx - 1
            x_end = maxx + 1
            wave_points = []

            # Generate the sine wave scanline
            num_steps = int(math.ceil((x_end - x_start) / resolution))
            for i in range(num_steps + 1):
                cx = x_start + i * resolution
                cy = y + amplitude * math.sin(2 * math.pi * cx / wavelength)
                wave_points.append((cx, cy))

            scanline = LineString(wave_points)
            intersection = p.intersection(scanline)

            if intersection.is_empty:
                y += spacing
                continue

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

            lines.sort(key=lambda l: l.coords[0][0])
            if not left_to_right:
                lines.reverse()

            for line in lines:
                if angle != 0.0:
                    line = affinity.rotate(line, angle, origin=centroid)

                coords = list(line.coords)
                if not left_to_right:
                    coords.reverse()
                all_fill_paths.append(coords)

            left_to_right = not left_to_right
            y += spacing

    return all_fill_paths


def generate_concentric_fill(points, spacing):
    """
    Generates concentric (inset) fill paths for a closed polygon.
    """
    if len(points) < 4:
        return []

    poly = Polygon(points)

    if not poly.is_valid or poly.area == 0:
        poly = poly.buffer(0)
        if poly.area == 0:
            return []

    all_fill_paths = []

    # Start the first inset inside the boundary
    current_geom = poly.buffer(-spacing)

    while not current_geom.is_empty and current_geom.area > 0:
        # Buffer can sometimes split a polygon into multiple islands (MultiPolygon)
        # Handle both standard Polygons and MultiPolygons
        polygons = [
            current_geom
        ] if current_geom.geom_type == 'Polygon' else list(current_geom.geoms)

        for p in polygons:
            # Extract the outer boundary of the inset shape
            if p.exterior:
                all_fill_paths.append(list(p.exterior.coords))

            # If the shape has holes, extract their boundaries as well
            for interior in p.interiors:
                all_fill_paths.append(list(interior.coords))

        # Shrink the geometry again for the next loop iteration
        current_geom = current_geom.buffer(-spacing)

    return all_fill_paths
