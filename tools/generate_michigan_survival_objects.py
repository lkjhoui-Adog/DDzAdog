#!/usr/bin/env python3
import argparse
import json
import math
import time
import urllib.parse
import urllib.request
from array import array
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "terrain" / "exports" / "utm16n" / "terrain_builder_export_metadata.json"
ROADS = ROOT / "terrain" / "exports" / "utm16n" / "vectors" / "roads_utm16n_clipped.geojson"
HEIGHTMAP = ROOT / "workdrive" / "MichiganSurvival" / "source" / "michigan_survival_height_4096_water_carved.asc"
GIS_DIR = ROOT / "terrain" / "gis"
BUILDINGS_OSM = GIS_DIR / "overpass_traverse_city_buildings.json"
OUT_JSON = Path(r"C:\Users\Adog\Documents\MI-Server-Manager-2026.05.21.1455\servers\Adog\mpmissions\dayzOffline.MichiganSurvival\custom\MichiganSurvivalObjects.json")
OUT_REPORT = ROOT / "build" / "michigan_survival_objects_report.json"

ROAD_PRIMARY = "bldr_rds_asf1_25"
ROAD_RESIDENTIAL = "bldr_rds_city_25"
ROAD_RUNWAY = "bldr_rds_runway_main"

SMALL_BUILDINGS = [
    "bldr_house_1w01_red",
    "bldr_house_1w02_blue",
    "bldr_house_1w03_yellow",
    "bldr_house_1w04_yellow",
    "bldr_house_1w06_blue",
    "bldr_house_1w07_green",
    "bldr_house_1w08_blue",
]

MEDIUM_BUILDINGS = [
    "bldr_house_2w01_yellow",
    "bldr_house_2w04_blue",
    "bldr_Shed_Open_Small_Complete",
    "bldr_BusStation_roof_big",
]

LARGE_BUILDINGS = [
    "bldr_Shed_Open_Big_Complete",
    "bldr_Shed_Open_Big2_Complete",
    "bldr_airport_small_main",
    "bldr_radio_building_east",
]

DOWNTOWN_CENTER = (4666.0, 5083.0)
AIRPORT_CENTER = (8081.0, 2653.0)
GARFIELD_CENTER = (1886.0, 4715.0)
SEED_CENTERS = [DOWNTOWN_CENTER, AIRPORT_CENTER, GARFIELD_CENTER]
PLAYER_TEST_CENTER = (6460.0, 4224.0)


def load_metadata():
    return json.loads(METADATA.read_text(encoding="utf-8"))


def latlon_to_utm16n(lat, lon):
    a = 6378137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    lon0 = math.radians(-87.0)
    sin_lat = math.sin(lat_r)
    cos_lat = math.cos(lat_r)
    tan_lat = math.tan(lat_r)
    n = a / math.sqrt(1 - e2 * sin_lat * sin_lat)
    t = tan_lat * tan_lat
    c = ep2 * cos_lat * cos_lat
    aa = cos_lat * (lon_r - lon0)
    m = a * (
        (1 - e2 / 4 - 3 * e2 * e2 / 64 - 5 * e2**3 / 256) * lat_r
        - (3 * e2 / 8 + 3 * e2 * e2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * lat_r)
        + (15 * e2 * e2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * lat_r)
        - (35 * e2**3 / 3072) * math.sin(6 * lat_r)
    )
    easting = k0 * n * (
        aa
        + (1 - t + c) * aa**3 / 6
        + (5 - 18 * t + t * t + 72 * c - 58 * ep2) * aa**5 / 120
    ) + 500000.0
    northing = k0 * (
        m
        + n
        * tan_lat
        * (
            aa * aa / 2
            + (5 - t + 9 * c + 4 * c * c) * aa**4 / 24
            + (61 - 58 * t + t * t + 600 * c - 330 * ep2) * aa**6 / 720
        )
    )
    return easting, northing


class HeightSampler:
    def __init__(self, path):
        self.path = path
        self.header = {}
        self.values = array("f")
        with path.open("r", encoding="utf-8") as handle:
            for _ in range(6):
                key, value = handle.readline().split()[:2]
                self.header[key.lower()] = float(value)
            self.ncols = int(self.header["ncols"])
            self.nrows = int(self.header["nrows"])
            for line in handle:
                self.values.extend(float(value) for value in line.split())
        expected = self.ncols * self.nrows
        if len(self.values) != expected:
            raise RuntimeError(f"Heightmap has {len(self.values)} values, expected {expected}")
        self.xll = self.header["xllcorner"]
        self.yll = self.header["yllcorner"]
        self.cell = self.header["cellsize"]
        self.top = self.yll + self.nrows * self.cell

    def sample_game(self, game_x, game_z):
        col = int(round(game_x / self.cell))
        row = int(round((10000.0 - game_z) / self.cell))
        col = max(0, min(self.ncols - 1, col))
        row = max(0, min(self.nrows - 1, row))
        return float(self.values[row * self.ncols + col])


def game_xy_from_utm(easting, northing, bounds):
    return easting - bounds["west"], northing - bounds["south"]


def inside_map(x, z, margin=0.0):
    return margin <= x <= 10000.0 - margin and margin <= z <= 10000.0 - margin


def dist2_to_centers(x, z):
    return min((x - cx) ** 2 + (z - cz) ** 2 for cx, cz in SEED_CENTERS)


def road_lines(feature, bounds):
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates") or []
    if geom.get("type") == "LineString":
        coords = [coords]
    for line in coords:
        converted = [game_xy_from_utm(pt[0], pt[1], bounds) for pt in line]
        converted = [(x, z) for x, z in converted if inside_map(x, z)]
        if len(converted) >= 2:
            yield converted


def add_obj(objects, name, x, y, z, yaw=0.0, pitch=0.0, roll=0.0, scale=1.0):
    objects.append(
        {
            "name": name,
            "pos": [round(x, 3), round(y, 3), round(z, 3)],
            "ypr": [round(yaw, 3), round(pitch, 3), round(roll, 3)],
            "scale": round(scale, 3),
            "enableCEPersistency": False,
        }
    )


def place_road_segments(features, bounds, heights, model, max_objects, step=24.5):
    objects = []
    skipped_water = 0
    for feature in features:
        for line in road_lines(feature, bounds):
            for a, b in zip(line, line[1:]):
                ax, az = a
                bx, bz = b
                dx = bx - ax
                dz = bz - az
                length = math.hypot(dx, dz)
                if length < 7.0:
                    continue
                yaw = math.degrees(math.atan2(dx, dz))
                count = max(1, int(round(length / step)))
                for idx in range(count):
                    t = (idx + 0.5) / count
                    x = ax + dx * t
                    z = az + dz * t
                    if not inside_map(x, z, margin=4.0):
                        continue
                    y = heights.sample_game(x, z)
                    if y < -1.0:
                        skipped_water += 1
                        continue
                    add_obj(objects, model, x, y + 0.035, z, yaw)
                    if len(objects) >= max_objects:
                        return objects, skipped_water
    return objects, skipped_water


def road_sort_key(feature, bounds):
    best = 10**12
    for line in road_lines(feature, bounds):
        for x, z in line:
            best = min(best, dist2_to_centers(x, z))
    return best


def generate_roads(bounds, heights, max_primary, max_residential):
    data = json.loads(ROADS.read_text(encoding="utf-8"))
    primary = []
    residential = []
    for feature in data.get("features", []):
        highway = (feature.get("properties") or {}).get("highway", "")
        if highway == "primary":
            primary.append(feature)
        elif highway == "residential":
            residential.append(feature)
    residential.sort(key=lambda f: road_sort_key(f, bounds))
    primary_objects, primary_water = place_road_segments(primary, bounds, heights, ROAD_PRIMARY, max_primary)
    residential_objects, residential_water = place_road_segments(
        residential, bounds, heights, ROAD_RESIDENTIAL, max_residential
    )
    return primary_objects + residential_objects, {
        "primaryFeatures": len(primary),
        "residentialFeaturesConsidered": len(residential),
        "primaryObjects": len(primary_objects),
        "residentialObjects": len(residential_objects),
        "roadObjectsSkippedAsWater": primary_water + residential_water,
    }


def overpass_bbox(meta):
    center = meta["centerWgs84"]
    lat = center["latitude"]
    lon = center["longitude"]
    half = meta["sizeMeters"] / 2
    lat_delta = half / 111320.0 + 0.012
    lon_delta = half / (111320.0 * math.cos(math.radians(lat))) + 0.012
    return lat - lat_delta, lon - lon_delta, lat + lat_delta, lon + lon_delta


def download_buildings(meta, refresh=False):
    if BUILDINGS_OSM.exists() and not refresh:
        return False
    south, west, north, east = overpass_bbox(meta)
    query = f"""
[out:json][timeout:180];
(
  way["building"]({south:.7f},{west:.7f},{north:.7f},{east:.7f});
);
out body;
>;
out skel qt;
"""
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    request = urllib.request.Request(
        "https://overpass-api.de/api/interpreter",
        data=data,
        headers={"User-Agent": "MichiganSurvivalDayZMapBuilder/1.0"},
    )
    GIS_DIR.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=240) as response:
        BUILDINGS_OSM.write_bytes(response.read())
    return True


def polygon_area(points):
    total = 0.0
    for a, b in zip(points, points[1:] + points[:1]):
        total += a[0] * b[1] - b[0] * a[1]
    return abs(total) * 0.5


def polygon_centroid(points):
    area_twice = 0.0
    cx = 0.0
    cz = 0.0
    for a, b in zip(points, points[1:] + points[:1]):
        cross = a[0] * b[1] - b[0] * a[1]
        area_twice += cross
        cx += (a[0] + b[0]) * cross
        cz += (a[1] + b[1]) * cross
    if abs(area_twice) < 0.001:
        return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)
    return cx / (3 * area_twice), cz / (3 * area_twice)


def longest_edge_yaw(points):
    best_len = 0.0
    best_yaw = 0.0
    for a, b in zip(points, points[1:] + points[:1]):
        dx = b[0] - a[0]
        dz = b[1] - a[1]
        length = math.hypot(dx, dz)
        if length > best_len:
            best_len = length
            best_yaw = math.degrees(math.atan2(dx, dz))
    return best_yaw


def model_for_building(area, idx):
    if area < 230:
        palette = SMALL_BUILDINGS
    elif area < 700:
        palette = MEDIUM_BUILDINGS
    else:
        palette = LARGE_BUILDINGS
    return palette[idx % len(palette)]


def generate_osm_buildings(bounds, heights, max_buildings):
    if not BUILDINGS_OSM.exists():
        return [], {"source": "missing", "waysRead": 0, "objects": 0, "skippedWater": 0}
    osm = json.loads(BUILDINGS_OSM.read_text(encoding="utf-8"))
    nodes = {}
    for element in osm.get("elements", []):
        if element.get("type") == "node":
            nodes[element["id"]] = (element["lat"], element["lon"])
    candidates = []
    skipped_water = 0
    for element in osm.get("elements", []):
        if element.get("type") != "way" or "building" not in (element.get("tags") or {}):
            continue
        points = []
        for node_id in element.get("nodes", []):
            if node_id not in nodes:
                continue
            lat, lon = nodes[node_id]
            easting, northing = latlon_to_utm16n(lat, lon)
            points.append(game_xy_from_utm(easting, northing, bounds))
        if len(points) < 4:
            continue
        if points[0] == points[-1]:
            points = points[:-1]
        cx, cz = polygon_centroid(points)
        if not inside_map(cx, cz, margin=12.0):
            continue
        area = polygon_area(points)
        if area < 25 or area > 8000:
            continue
        y = heights.sample_game(cx, cz)
        if y < 0.2:
            skipped_water += 1
            continue
        candidates.append(
            {
                "x": cx,
                "z": cz,
                "y": y + 0.08,
                "yaw": longest_edge_yaw(points),
                "area": area,
                "rank": dist2_to_centers(cx, cz),
                "osmId": element["id"],
            }
        )
    candidates.sort(key=lambda item: (item["rank"], -item["area"]))
    objects = []
    for idx, candidate in enumerate(candidates[:max_buildings]):
        add_obj(
            objects,
            model_for_building(candidate["area"], idx),
            candidate["x"],
            candidate["y"],
            candidate["z"],
            candidate["yaw"],
        )
    return objects, {
        "source": str(BUILDINGS_OSM),
        "waysRead": sum(1 for e in osm.get("elements", []) if e.get("type") == "way"),
        "candidatesInsideMap": len(candidates),
        "objects": len(objects),
        "skippedWater": skipped_water,
    }


def add_landmark(objects, heights, model, x, z, yaw=0.0, scale=1.0, y_offset=0.08):
    if inside_map(x, z):
        add_obj(objects, model, x, heights.sample_game(x, z) + y_offset, z, yaw, scale=scale)


def generate_landmarks(heights):
    objects = []
    # Downtown starter compositions: denser blocks and public-service silhouettes.
    downtown_models = [
        "bldr_house_2w01_yellow",
        "bldr_house_2w04_blue",
        "bldr_Shed_Open_Big_Complete",
        "bldr_airport_small_main",
    ]
    downtown_positions = [
        (4540, 5110, 82),
        (4635, 5145, 82),
        (4740, 5090, 82),
        (4845, 5050, 82),
        (4580, 4930, 172),
        (4700, 4890, 172),
        (4820, 4925, 172),
        (4935, 4970, 172),
    ]
    for idx, (x, z, yaw) in enumerate(downtown_positions):
        add_landmark(objects, heights, downtown_models[idx % len(downtown_models)], x, z, yaw)

    special = [
        ("bldr_mobilelaboratory", 5260, 4380, 35),
        ("bldr_City_FireStation_Int", 5050, 4650, 25),
        ("bldr_Misc_TrafficLights", 4430, 4700, 100),
        ("bldr_FuelStation_Shed", 6420, 3650, 78),
        ("bldr_FuelStation_Sign", 6460, 3640, 78),
        ("bldr_BusStation_roof_long", 4300, 5150, 82),
        ("bldr_BusStation_wall_bench", 4370, 5195, 82),
    ]
    for model, x, z, yaw in special:
        add_landmark(objects, heights, model, x, z, yaw)

    # Cherry Capital Airport starter: runway surface, hangars, and a control building.
    for x in range(7050, 8950, 125):
        add_landmark(objects, heights, ROAD_RUNWAY, x, 2520, 84, y_offset=0.04)
    airport = [
        ("bldr_airport_small_hangar", 7750, 2775, 170),
        ("bldr_airport_small_hangar2", 7925, 2770, 170),
        ("bldr_airport_small_main", 8150, 2810, 170),
        ("bldr_BusStation_roof_big", 8300, 2860, 170),
    ]
    for model, x, z, yaw in airport:
        add_landmark(objects, heights, model, x, z, yaw)

    return objects


def generate_test_plaza(heights):
    objects = []
    center_x, center_z = PLAYER_TEST_CENTER

    # Proof area at the last confirmed player login spot. The mission spawner
    # snaps this layer to the live terrain height, so these source heights only
    # need to be close enough for offline inspection.
    for offset in range(-75, 76, 25):
        add_landmark(objects, heights, ROAD_RESIDENTIAL, center_x + offset, center_z, 90, y_offset=0.04)
        add_landmark(objects, heights, ROAD_RESIDENTIAL, center_x, center_z + offset, 0, y_offset=0.04)

    plaza_buildings = [
        ("bldr_house_1w01_red", center_x - 58, center_z - 38, 35),
        ("bldr_house_1w02_blue", center_x - 42, center_z + 52, 120),
        ("bldr_house_2w01_yellow", center_x + 54, center_z - 48, 210),
        ("bldr_Shed_Open_Big_Complete", center_x + 84, center_z + 36, 305),
        ("bldr_airport_small_main", center_x - 95, center_z + 84, 140),
        ("bldr_BusStation_roof_big", center_x + 18, center_z - 82, 90),
    ]
    for model, x, z, yaw in plaza_buildings:
        add_landmark(objects, heights, model, x, z, yaw, y_offset=0.12)

    lights = [
        ("bldr_Lamp_City1", center_x - 34, center_z - 34, 0),
        ("bldr_Lamp_City2", center_x + 34, center_z - 34, 0),
        ("bldr_Lamp_City3", center_x - 34, center_z + 34, 0),
        ("bldr_Lamp_City1", center_x + 34, center_z + 34, 0),
    ]
    for model, x, z, yaw in lights:
        add_landmark(objects, heights, model, x, z, yaw, y_offset=0.12)

    water_tests = [
        ("bldr_pond_big_29_01", center_x + 112, center_z + 86, 0),
        ("bldr_streambed_long_straight_water", center_x + 128, center_z + 38, 90),
    ]
    for model, x, z, yaw in water_tests:
        add_landmark(objects, heights, model, x, z, yaw, y_offset=0.02)

    return objects


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-buildings", action="store_true")
    parser.add_argument("--max-primary-roads", type=int, default=420)
    parser.add_argument("--max-residential-roads", type=int, default=520)
    parser.add_argument("--max-buildings", type=int, default=140)
    args = parser.parse_args()

    meta = load_metadata()
    bounds = meta["boundsUtm16n"]
    heights = HeightSampler(HEIGHTMAP)

    building_downloaded = False
    building_download_error = None
    try:
        building_downloaded = download_buildings(meta, refresh=args.refresh_buildings)
    except Exception as exc:
        building_download_error = str(exc)

    road_objects, road_report = generate_roads(bounds, heights, args.max_primary_roads, args.max_residential_roads)
    building_objects, building_report = generate_osm_buildings(bounds, heights, args.max_buildings)
    landmark_objects = generate_landmarks(heights)
    test_plaza_objects = generate_test_plaza(heights)

    objects = road_objects + building_objects + landmark_objects + test_plaza_objects
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({"Objects": objects}, indent=2), encoding="utf-8")

    report = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "output": str(OUT_JSON),
        "totalObjects": len(objects),
        "roads": road_report,
        "buildings": building_report,
        "buildingDownloadAttempted": True,
        "buildingDownloadRefreshed": building_downloaded,
        "buildingDownloadError": building_download_error,
        "landmarkObjects": len(landmark_objects),
        "testPlazaObjects": len(test_plaza_objects),
        "testPlazaCenter": {"x": PLAYER_TEST_CENTER[0], "z": PLAYER_TEST_CENTER[1]},
        "sources": {
            "roads": str(ROADS),
            "heightmap": str(HEIGHTMAP),
            "buildings": str(BUILDINGS_OSM),
        },
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
