import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from shapely import line_merge, union_all
from shapely.geometry import LineString, MultiLineString, shape


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT = ROOT / "terrain" / "exports" / "michigan-lower-peninsula"
DEFAULT_METADATA = DEFAULT_EXPORT / "terrain_builder_export_metadata.json"
DEFAULT_MAJOR_ROADS = DEFAULT_EXPORT / "vectors" / "major_roads_world.geojson"
DEFAULT_HOMETOWN_ROADS = DEFAULT_EXPORT / "vectors" / "hometown_roads_world.geojson"
DEFAULT_HEIGHTMAP = ROOT / "workdrive" / "MichiganMitten-Statewide" / "source" / "michigan_mitten_height_4096.asc"
DEFAULT_OUTPUT = ROOT / "server-files" / "michigan-mitten-statewide" / "mpmissions" / "dayzOffline.MichiganMitten" / "custom" / "MichiganMittenObjects.json"
DEFAULT_REPORT = ROOT / "build" / "michigan_mitten_roads_report.json"
DEFAULT_PREVIEW = ROOT / "build" / "diagnostics" / "michigan-mitten-road-objects.png"

ROAD_ASPHALT = "bldr_rds_asf1_25"
ROAD_CITY = "bldr_rds_city_25"
PANEL_LENGTH = 24.5


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def normalize_ref(value):
    if not value:
        return []
    return [part.strip().upper().replace("-", " ") for part in value.split(";") if part.strip()]


def geometry_lines(geometry):
    if isinstance(geometry, LineString):
        return [geometry]
    if isinstance(geometry, MultiLineString):
        return list(geometry.geoms)
    return []


def load_selected_major(path, route_order):
    data = read_json(path)
    routes = {route: [] for route in route_order}
    feature_counts = defaultdict(int)
    for feature in data.get("features", []):
        properties = feature.get("properties") or {}
        highway = properties.get("highway") or ""
        if highway.endswith("_link"):
            continue
        refs = normalize_ref(properties.get("ref"))
        matched = next((route for route in route_order if route in refs), None)
        if matched is None:
            continue
        geometry = shape(feature["geometry"])
        for line in geometry_lines(geometry):
            if line.length >= 5.0:
                routes[matched].append(line)
                feature_counts[matched] += 1
    return routes, feature_counts


def load_hometown(path):
    data = read_json(path)
    groups = defaultdict(list)
    for feature in data.get("features", []):
        properties = feature.get("properties") or {}
        highway = properties.get("highway") or "unclassified"
        name = properties.get("name") or "unnamed"
        model = ROAD_ASPHALT if highway in {"motorway", "trunk", "primary", "secondary"} else ROAD_CITY
        geometry = shape(feature["geometry"])
        for line in geometry_lines(geometry):
            if line.length >= 5.0:
                groups[(name, highway, model)].append(line)
    return groups


def merged_lines(lines):
    if not lines:
        return []
    merged = line_merge(union_all(lines))
    return geometry_lines(merged)


class HeightSampler:
    def __init__(self, path):
        self.path = Path(path)
        header = {}
        with self.path.open("r", encoding="ascii") as handle:
            for _ in range(6):
                key, value = handle.readline().split()[:2]
                header[key.lower()] = float(value)
        self.ncols = int(header["ncols"])
        self.nrows = int(header["nrows"])
        self.cell = float(header["cellsize"])
        self.xll = float(header.get("xllcorner", 0.0))
        self.yll = float(header.get("yllcorner", 0.0))
        self.world_height = self.nrows * self.cell
        self.values = np.loadtxt(self.path, skiprows=6, dtype=np.float32)
        if self.values.shape != (self.nrows, self.ncols):
            raise RuntimeError(f"Unexpected heightmap shape {self.values.shape}")

    def sample(self, x, z):
        col = int(round((x - self.xll) / self.cell))
        row = int(round((self.world_height - (z - self.yll)) / self.cell))
        col = max(0, min(self.ncols - 1, col))
        row = max(0, min(self.nrows - 1, row))
        return float(self.values[row, col])


def road_object(model, x, y, z, yaw, pitch):
    return {
        "name": model,
        "pos": [round(x, 3), round(y + 0.045, 3), round(z, 3)],
        "ypr": [round(yaw % 360.0, 3), round(pitch, 3), 0.0],
        "scale": 1.0,
        "enableCEPersistency": False,
    }


def line_panels(line, model, heights, occupied, limit):
    objects = []
    skipped_water = 0
    if line.length < 8.0 or limit <= 0:
        return objects, skipped_water
    count = max(1, int(round(line.length / PANEL_LENGTH)))
    spacing = line.length / count
    for index in range(count):
        if len(objects) >= limit:
            break
        distance = (index + 0.5) * spacing
        center = line.interpolate(distance)
        tangent = min(6.0, spacing * 0.35, line.length * 0.2)
        before = line.interpolate(max(0.0, distance - tangent))
        after = line.interpolate(min(line.length, distance + tangent))
        dx = after.x - before.x
        dz = after.y - before.y
        if abs(dx) + abs(dz) < 0.001:
            continue
        yaw = math.degrees(math.atan2(dx, dz))
        center_height = heights.sample(center.x, center.y)
        before_height = heights.sample(before.x, before.y)
        after_height = heights.sample(after.x, after.y)
        if min(center_height, before_height, after_height) < 0.0:
            skipped_water += 1
            continue
        horizontal = max(math.hypot(dx, dz), 0.001)
        pitch = max(-12.0, min(12.0, math.degrees(math.atan2(after_height - before_height, horizontal))))
        direction_bucket = int(round((yaw % 180.0) / 8.0))
        key = (int(round(center.x / 3.0)), int(round(center.y / 3.0)), direction_bucket)
        if key in occupied:
            continue
        occupied.add(key)
        objects.append(road_object(model, center.x, center_height, center.y, yaw, pitch))
    return objects, skipped_water


def generate_hometown(groups, heights, occupied, limit):
    objects = []
    skipped_water = 0
    ordered = sorted(
        groups.items(),
        key=lambda item: (
            0 if item[0][1] in {"motorway", "trunk", "primary", "secondary"} else 1,
            item[0][0].casefold(),
        ),
    )
    for (name, highway, model), source_lines in ordered:
        for line in merged_lines(source_lines):
            created, skipped = line_panels(line, model, heights, occupied, limit - len(objects))
            objects.extend(created)
            skipped_water += skipped
            if len(objects) >= limit:
                return objects, skipped_water
    return objects, skipped_water


def generate_statewide(routes, route_order, heights, occupied, limit):
    objects = []
    skipped_water = 0
    route_counts = {}
    for route in route_order:
        route_start = len(objects)
        for line in merged_lines(routes.get(route, [])):
            created, skipped = line_panels(line, ROAD_ASPHALT, heights, occupied, limit - len(objects))
            objects.extend(created)
            skipped_water += skipped
            if len(objects) >= limit:
                break
        route_counts[route] = len(objects) - route_start
        if len(objects) >= limit:
            break
    return objects, skipped_water, route_counts


def save_preview(path, metadata, objects):
    satellite_path = ROOT / "terrain" / "terrain-builder" / "MichiganMitten-Statewide" / "source" / "michigan_mitten_sat_lco.png"
    with Image.open(satellite_path) as source:
        image = source.convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)
    world_size = float(metadata["sizeMeters"])
    for item in objects:
        x = item["pos"][0] / world_size * image.width
        y = image.height - item["pos"][2] / world_size * image.height
        color = (255, 225, 80) if item["name"] == ROAD_CITY else (245, 245, 245)
        draw.point((x, y), fill=color)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main():
    parser = argparse.ArgumentParser(description="Generate a roads-only MichiganMitten mission object layer.")
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA))
    parser.add_argument("--major-roads", default=str(DEFAULT_MAJOR_ROADS))
    parser.add_argument("--hometown-roads", default=str(DEFAULT_HOMETOWN_ROADS))
    parser.add_argument("--heightmap", default=str(DEFAULT_HEIGHTMAP))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--preview", default=str(DEFAULT_PREVIEW))
    parser.add_argument("--routes", default="I 75,I 94,I 96,US 131,US 23")
    parser.add_argument("--max-statewide", type=int, default=16000)
    parser.add_argument("--max-hometown", type=int, default=3500)
    args = parser.parse_args()

    route_order = [route.strip().upper().replace("-", " ") for route in args.routes.split(",") if route.strip()]
    metadata = read_json(args.metadata)
    heights = HeightSampler(args.heightmap)
    routes, source_route_counts = load_selected_major(args.major_roads, route_order)
    hometown_groups = load_hometown(args.hometown_roads)
    occupied = set()

    hometown_objects, hometown_water = generate_hometown(
        hometown_groups,
        heights,
        occupied,
        args.max_hometown,
    )
    statewide_objects, statewide_water, route_object_counts = generate_statewide(
        routes,
        route_order,
        heights,
        occupied,
        args.max_statewide,
    )
    objects = hometown_objects + statewide_objects

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"Objects": objects}, indent=2), encoding="utf-8")
    report = {
        "output": str(output),
        "totalObjects": len(objects),
        "hometownObjects": len(hometown_objects),
        "statewideObjects": len(statewide_objects),
        "skippedWater": hometown_water + statewide_water,
        "routes": route_order,
        "sourceRouteFeatures": dict(source_route_counts),
        "routeObjectCounts": route_object_counts,
        "models": {"statewide": ROAD_ASPHALT, "hometownLocal": ROAD_CITY},
        "panelLengthMeters": PANEL_LENGTH,
    }
    report_path = Path(args.report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    save_preview(Path(args.preview).resolve(), metadata, objects)

    print(f"Road object layer: {output}")
    print(f"Total objects: {len(objects)}")
    print(f"Hometown objects: {len(hometown_objects)}")
    print(f"Statewide objects: {len(statewide_objects)}")
    print(f"Route objects: {route_object_counts}")
    print(f"Skipped over water: {hometown_water + statewide_water}")


if __name__ == "__main__":
    main()
