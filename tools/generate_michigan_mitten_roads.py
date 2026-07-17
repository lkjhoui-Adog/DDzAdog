import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from shapely import line_merge, union_all
from shapely.geometry import LineString, MultiLineString, Point, shape


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT = ROOT / "terrain" / "exports" / "michigan-lower-peninsula"
DEFAULT_METADATA = DEFAULT_EXPORT / "terrain_builder_export_metadata.json"
DEFAULT_MAJOR_ROADS = DEFAULT_EXPORT / "vectors" / "major_roads_world.geojson"
DEFAULT_HOMETOWN_ROADS = DEFAULT_EXPORT / "vectors" / "hometown_roads_world.geojson"
DEFAULT_HEIGHTMAP = ROOT / "workdrive" / "MichiganMitten-Statewide" / "source" / "michigan_mitten_height_4096.asc"
DEFAULT_OUTPUT = ROOT / "server-files" / "michigan-mitten-statewide" / "mpmissions" / "dayzOffline.MichiganMitten" / "custom" / "MichiganMittenObjects.json"
DEFAULT_REPORT = ROOT / "build" / "michigan_mitten_roads_report.json"
DEFAULT_PREVIEW = ROOT / "build" / "diagnostics" / "michigan-mitten-road-objects.png"

ROAD_RURAL_2LANE = "MI_Road_Rural_2Lane_25"
ROAD_LOCAL_2LANE = "MI_Road_Local_2Lane_25"
ROAD_DIRT_2LANE = "MI_Road_Dirt_2Lane_25"
ROAD_URBAN_3LANE = "MI_Road_Urban_3Lane_25"
ROAD_URBAN_4LANE = "MI_Road_Urban_4Lane_25"
ROAD_FREEWAY_4LANE = "MI_Road_Freeway_4Lane_25"
DEFAULT_STATEWIDE_ROUTES = (
    "I 75",
    "I 94",
    "I 96",
    "I 69",
    "I 196",
    "I 275",
    "I 475",
    "I 496",
    "I 696",
    "US 10",
    "US 23",
    "US 31",
    "US 127",
    "US 131",
    "M 22",
    "M 59",
    "M 72",
)
PANEL_LENGTH = 24.5
ROAD_MODEL_VARIANTS = {
    ROAD_DIRT_2LANE: {
        25: "MI_Road_Dirt_2Lane_25",
        12: "MI_Road_Dirt_2Lane_12",
        6: "MI_Road_Dirt_2Lane_6",
    },
    ROAD_LOCAL_2LANE: {
        25: "MI_Road_Local_2Lane_25",
        12: "MI_Road_Local_2Lane_12",
        6: "MI_Road_Local_2Lane_6",
    },
    ROAD_RURAL_2LANE: {
        25: "MI_Road_Rural_2Lane_25",
        12: "MI_Road_Rural_2Lane_12",
        6: "MI_Road_Rural_2Lane_6",
    },
    ROAD_URBAN_3LANE: {
        25: "MI_Road_Urban_3Lane_25",
        12: "MI_Road_Urban_3Lane_12",
        6: "MI_Road_Urban_3Lane_6",
    },
    ROAD_URBAN_4LANE: {
        25: "MI_Road_Urban_4Lane_25",
        12: "MI_Road_Urban_4Lane_12",
        6: "MI_Road_Urban_4Lane_6",
    },
    ROAD_FREEWAY_4LANE: {
        25: "MI_Road_Freeway_4Lane_25",
        12: "MI_Road_Freeway_4Lane_12",
        6: "MI_Road_Freeway_4Lane_6",
    },
}
ROAD_MODEL_PRIORITY = {
    ROAD_DIRT_2LANE: 0,
    ROAD_LOCAL_2LANE: 0,
    ROAD_RURAL_2LANE: 1,
    ROAD_URBAN_3LANE: 2,
    ROAD_URBAN_4LANE: 3,
    ROAD_FREEWAY_4LANE: 4,
}
PANEL_LENGTHS = {25: 24.5, 12: 12.25, 6: 6.125}
PANEL_CELLS = {25: 4, 12: 2, 6: 1}
PANEL_SELECTION_ORDER = (25, 12, 6)
ROUGHNESS_LIMITS = {25: 0.30, 12: 0.18}
FOOTPRINT_ROUGHNESS_LIMITS = {25: 0.045, 12: 0.025}
CURVATURE_LIMITS = {25: 0.6, 12: 0.8, 6: 0.8}
CURVE_ANGLES = tuple(range(1, 31))
MAX_LONG_MODULE_CURVATURE = 30.0
ROAD_PLACEMENT_OFFSET = 0.001
SOURCE_SAMPLE_INTERVAL = 3.0
SOURCE_SMOOTH_WINDOW = 30.0
SOURCE_SMOOTH_MAX_DEVIATION = 6.0
SCENIC_SOURCE_SMOOTH_WINDOW = 48.0
SCENIC_SOURCE_SMOOTH_MAX_DEVIATION = 10.0
HOMETOWN_SOURCE_SMOOTH_WINDOW = 42.0
HOMETOWN_SOURCE_SMOOTH_MAX_DEVIATION = 8.0
FRAGMENT_JOIN_MAX_GAP = 14.0
FRAGMENT_JOIN_MAX_ANGLE = 35.0
FRAGMENT_JOIN_COUNT = 0
PRUNED_SHORT_BRANCH_COUNT = 0
REMOVED_SHORT_LOOP_COUNT = 0
SKIPPED_SHORT_ACUTE_COUNT = 0
DEDUPLICATION_LONGITUDINAL = 5.0
DEDUPLICATION_LATERAL = {
    ROAD_DIRT_2LANE: 3.0,
    ROAD_LOCAL_2LANE: 3.2,
    ROAD_RURAL_2LANE: 3.5,
    ROAD_URBAN_3LANE: 6.0,
    ROAD_URBAN_4LANE: 10.0,
    ROAD_FREEWAY_4LANE: 18.0,
}
ROAD_HALF_WIDTHS = {
    ROAD_DIRT_2LANE: 3.0,
    ROAD_LOCAL_2LANE: 3.3,
    ROAD_RURAL_2LANE: 3.8,
    ROAD_URBAN_3LANE: 5.6,
    ROAD_URBAN_4LANE: 7.6,
    ROAD_FREEWAY_4LANE: 9.5,
}
DEDUPLICATION_ANGLE = 12.0
SAME_ROAD_DEDUPLICATION_LONGITUDINAL = 5.0
SAME_ROAD_DEDUPLICATION_ANGLE = 28.0
SAME_ROAD_LATERAL_MULTIPLIER = 1.5
STATEWIDE_LOOP_MAX_PATH_DISTANCE = 160.0
STATEWIDE_LOOP_CLOSURE_DISTANCE = 15.0
SHORT_CLOSED_LOOP_MAX_LENGTH = 180.0
SHORT_CLOSED_LOOP_MAX_CLOSURE = 20.0
CONSERVATIVE_DEDUPLICATION_LONGITUDINAL = 3.2
CONSERVATIVE_DEDUPLICATION_LATERAL = 0.75
CONSERVATIVE_DEDUPLICATION_ANGLE = 8.0


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


def route_principal_axis(lines):
    coordinates = np.asarray(
        [coordinate for line in lines for coordinate in line.coords],
        dtype=np.float64,
    )
    if len(coordinates) < 2:
        return np.asarray((1.0, 0.0), dtype=np.float64)
    centered = coordinates - coordinates.mean(axis=0)
    covariance = centered.T @ centered
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    axis = eigenvectors[:, int(np.argmax(eigenvalues))]
    dominant = 0 if abs(axis[0]) >= abs(axis[1]) else 1
    if axis[dominant] < 0.0:
        axis = -axis
    return axis


def component_direction_score(line, axis):
    start = line.coords[0]
    end = line.coords[-1]
    delta_x = end[0] - start[0]
    delta_z = end[1] - start[1]
    score = delta_x * axis[0] + delta_z * axis[1]
    if abs(score) >= max(0.5, line.length * 0.01):
        return score
    return delta_x if abs(delta_x) >= abs(delta_z) else delta_z


def select_statewide_corridor(records):
    one_way_lines = []
    two_way_lines = []
    for line, oneway in records:
        if oneway in {"yes", "-1"}:
            if oneway == "-1":
                line = LineString(reversed(line.coords))
            one_way_lines.append(line)
        else:
            two_way_lines.append(line)

    if not one_way_lines:
        return two_way_lines, {
            "oneWaySourceLines": 0,
            "directedComponents": 0,
            "selectedDirectedComponents": 0,
            "twoWaySourceLines": len(two_way_lines),
            "axis": [1.0, 0.0],
        }

    axis = route_principal_axis(one_way_lines)
    directed = line_merge(MultiLineString(one_way_lines), directed=True)
    directed_components = geometry_lines(directed)
    selected = [
        line
        for line in directed_components
        if component_direction_score(line, axis) >= 0.0
    ]
    report = {
        "oneWaySourceLines": len(one_way_lines),
        "directedComponents": len(directed_components),
        "selectedDirectedComponents": len(selected),
        "twoWaySourceLines": len(two_way_lines),
        "axis": [round(float(axis[0]), 6), round(float(axis[1]), 6)],
        "selectedLengthMeters": round(sum(line.length for line in selected), 3),
        "discardedOpposingLengthMeters": round(
            sum(line.length for line in directed_components) - sum(line.length for line in selected),
            3,
        ),
    }
    return selected + two_way_lines, report


def load_selected_major(path, route_order, carriageway_mode):
    data = read_json(path)
    route_records = {route: [] for route in route_order}
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
                oneway = str(properties.get("oneway") or "no").lower()
                route_records[matched].append((line, oneway))
                feature_counts[matched] += 1

    routes = {}
    corridor_report = {}
    for route in route_order:
        records = route_records[route]
        if carriageway_mode == "single-direction":
            routes[route], corridor_report[route] = select_statewide_corridor(records)
        else:
            routes[route] = [line for line, _ in records]
            corridor_report[route] = {
                "sourceLines": len(records),
                "selectedLines": len(records),
            }
    return routes, feature_counts, corridor_report


def load_hometown(path):
    data = read_json(path)
    groups = defaultdict(list)
    for feature in data.get("features", []):
        properties = feature.get("properties") or {}
        highway = properties.get("highway") or "unclassified"
        if highway.endswith("_link"):
            continue
        name = properties.get("name") or "unnamed"
        if highway in {"motorway", "trunk"}:
            model = ROAD_FREEWAY_4LANE
        elif highway == "primary":
            model = ROAD_URBAN_4LANE
        elif highway in {"secondary", "tertiary"}:
            model = ROAD_URBAN_3LANE
        else:
            model = ROAD_RURAL_2LANE
        geometry = shape(feature["geometry"])
        for line in geometry_lines(geometry):
            if line.length >= 5.0:
                groups[(name, highway, model)].append(line)
    consolidated = defaultdict(list)
    named = defaultdict(list)
    named_models = defaultdict(list)
    for (name, highway, model), lines in groups.items():
        if name == "unnamed":
            consolidated[(name, highway, model)].extend(lines)
            continue
        named[name].extend(lines)
        named_models[name].append((ROAD_MODEL_PRIORITY[model], highway, model))
    for name, lines in named.items():
        _, highway, model = max(named_models[name])
        consolidated[(name, highway, model)].extend(lines)
    return consolidated


def smooth_line(line, window=SOURCE_SMOOTH_WINDOW, maximum_deviation=SOURCE_SMOOTH_MAX_DEVIATION):
    if line.length < SOURCE_SAMPLE_INTERVAL * 3.0:
        return line

    sample_count = max(4, int(math.ceil(line.length / SOURCE_SAMPLE_INTERVAL)) + 1)
    distances = np.linspace(0.0, line.length, sample_count)
    coordinates = np.asarray(
        [(line.interpolate(float(distance)).x, line.interpolate(float(distance)).y) for distance in distances],
        dtype=np.float64,
    )
    sample_spacing = line.length / (sample_count - 1)
    radius = max(1, int(round(window * 0.5 / sample_spacing)))
    offsets = np.arange(-radius, radius + 1, dtype=np.float64)
    weights = (radius + 1.0) - np.abs(offsets)
    weights /= weights.sum()
    padded = np.pad(coordinates, ((radius, radius), (0, 0)), mode="edge")
    smoothed = np.column_stack(
        [np.convolve(padded[:, axis], weights, mode="valid") for axis in range(2)]
    )

    displacement = smoothed - coordinates
    distance_from_source = np.linalg.norm(displacement, axis=1)
    scale = np.ones_like(distance_from_source)
    over_limit = distance_from_source > maximum_deviation
    scale[over_limit] = maximum_deviation / distance_from_source[over_limit]
    smoothed = coordinates + displacement * scale[:, None]
    smoothed[0] = coordinates[0]
    smoothed[-1] = coordinates[-1]
    candidate = LineString(smoothed)
    return candidate if candidate.is_valid and candidate.length >= 5.0 else line


def signed_angle_delta(first, second):
    return ((second - first + 180.0) % 360.0) - 180.0


def point_heading(first, second):
    return math.degrees(math.atan2(second[0] - first[0], second[1] - first[1]))


def fragment_join_candidate(first, second, reject_closed_loops=False):
    first_coordinates = list(first.coords)
    second_coordinates = list(second.coords)
    best = None
    for reverse_first in (False, True):
        first_oriented = list(reversed(first_coordinates)) if reverse_first else first_coordinates
        for reverse_second in (False, True):
            second_oriented = list(reversed(second_coordinates)) if reverse_second else second_coordinates
            first_end = first_oriented[-1]
            second_start = second_oriented[0]
            distance = math.dist(first_end, second_start)
            if distance > FRAGMENT_JOIN_MAX_GAP:
                continue
            outgoing = point_heading(first_oriented[-2], first_end)
            incoming = point_heading(second_start, second_oriented[1])
            connector = point_heading(first_end, second_start) if distance > 0.001 else outgoing
            first_turn = abs(signed_angle_delta(outgoing, connector))
            second_turn = abs(signed_angle_delta(connector, incoming))
            if first_turn > FRAGMENT_JOIN_MAX_ANGLE or second_turn > FRAGMENT_JOIN_MAX_ANGLE:
                continue
            if reject_closed_loops:
                combined_length = first.length + distance + second.length
                closure = math.dist(first_oriented[0], second_oriented[-1])
                if combined_length >= 100.0 and closure <= STATEWIDE_LOOP_CLOSURE_DISTANCE:
                    continue
                candidate_coordinates = list(first_oriented)
                if distance > 0.001:
                    candidate_coordinates.append(second_oriented[0])
                candidate_coordinates.extend(second_oriented[1:])
                if not LineString(candidate_coordinates).is_simple:
                    continue
            score = distance + 0.04 * (first_turn + second_turn)
            candidate = score, distance, first_oriented, second_oriented
            if best is None or candidate[0] < best[0]:
                best = candidate
    return best


def connect_line_fragments(lines, reject_closed_loops=False):
    global FRAGMENT_JOIN_COUNT
    working = list(lines)
    if len(working) > 200:
        return working
    while len(working) > 1:
        best = None
        for first_index in range(len(working) - 1):
            for second_index in range(first_index + 1, len(working)):
                candidate = fragment_join_candidate(
                    working[first_index],
                    working[second_index],
                    reject_closed_loops,
                )
                if candidate is None:
                    continue
                score, distance, first_coordinates, second_coordinates = candidate
                record = score, first_index, second_index, distance, first_coordinates, second_coordinates
                if best is None or score < best[0]:
                    best = record
        if best is None:
            break
        _, first_index, second_index, distance, first_coordinates, second_coordinates = best
        joined_coordinates = list(first_coordinates)
        if distance > 0.001:
            joined_coordinates.append(second_coordinates[0])
        joined_coordinates.extend(second_coordinates[1:])
        joined = LineString(joined_coordinates)
        if not joined.is_valid or joined.length < 5.0:
            break
        working[first_index] = joined
        del working[second_index]
        FRAGMENT_JOIN_COUNT += 1
    return working


def prune_short_parallel_branches(lines):
    global PRUNED_SHORT_BRANCH_COUNT
    working = list(lines)
    changed = True
    while changed and len(working) > 1:
        changed = False
        for index, line in enumerate(working):
            if line.length > 80.0:
                continue
            other_geometry = union_all(working[:index] + working[index + 1 :])
            start = Point(line.coords[0])
            end = Point(line.coords[-1])
            if start.distance(other_geometry) <= 0.75 and end.distance(other_geometry) <= 0.75:
                del working[index]
                PRUNED_SHORT_BRANCH_COUNT += 1
                changed = True
                break
    return working


def remove_short_loops(
    line,
    maximum_path_distance=100.0,
    closure_distance_limit=3.0,
):
    global REMOVED_SHORT_LOOP_COUNT
    coordinates = list(line.coords)
    while len(coordinates) >= 4:
        cumulative = [0.0]
        for first, second in zip(coordinates, coordinates[1:]):
            cumulative.append(cumulative[-1] + math.dist(first, second))
        best = None
        for first_index in range(len(coordinates) - 2):
            for second_index in range(first_index + 2, len(coordinates)):
                path_distance = cumulative[second_index] - cumulative[first_index]
                if path_distance < 12.0 or path_distance > maximum_path_distance:
                    continue
                closure_distance = math.dist(coordinates[first_index], coordinates[second_index])
                if closure_distance > closure_distance_limit:
                    continue
                saved_distance = path_distance - closure_distance
                candidate = saved_distance, first_index, second_index
                if best is None or candidate[0] > best[0]:
                    best = candidate
        if best is None:
            break
        _, first_index, second_index = best
        coordinates = coordinates[: first_index + 1] + coordinates[second_index:]
        REMOVED_SHORT_LOOP_COUNT += 1
    candidate = LineString(coordinates)
    return candidate if candidate.is_valid and candidate.length >= 5.0 else line


def is_short_closed_loop(line):
    global REMOVED_SHORT_LOOP_COUNT
    if (
        line.length <= SHORT_CLOSED_LOOP_MAX_LENGTH
        and math.dist(line.coords[0], line.coords[-1]) <= SHORT_CLOSED_LOOP_MAX_CLOSURE
    ):
        REMOVED_SHORT_LOOP_COUNT += 1
        return True
    return False


def merged_lines(
    lines,
    join_fragments=True,
    smooth_window=SOURCE_SMOOTH_WINDOW,
    smooth_maximum_deviation=SOURCE_SMOOTH_MAX_DEVIATION,
    loop_maximum_path_distance=100.0,
    loop_closure_distance=3.0,
    reject_closed_fragment_loops=False,
):
    if not lines:
        return []
    merged = line_merge(union_all(lines), directed=reject_closed_fragment_loops)
    merged_parts = prune_short_parallel_branches(geometry_lines(merged))
    connected = (
        connect_line_fragments(merged_parts, reject_closed_fragment_loops)
        if join_fragments
        else merged_parts
    )
    output = []
    for line in connected:
        if is_short_closed_loop(line):
            continue
        repaired = remove_short_loops(
            line,
            loop_maximum_path_distance,
            loop_closure_distance,
        )
        if is_short_closed_loop(repaired):
            continue
        output.append(smooth_line(repaired, smooth_window, smooth_maximum_deviation))
    return output


def statewide_road_model(route):
    if route.startswith("I "):
        return ROAD_FREEWAY_4LANE
    if route in {"M 22", "M 72"}:
        return ROAD_RURAL_2LANE
    return ROAD_URBAN_4LANE


def statewide_smoothing(route):
    if route in {"M 22", "M 72"}:
        return SCENIC_SOURCE_SMOOTH_WINDOW, SCENIC_SOURCE_SMOOTH_MAX_DEVIATION
    return SOURCE_SMOOTH_WINDOW, SOURCE_SMOOTH_MAX_DEVIATION


def maximum_vertex_turn(line):
    coordinates = list(line.coords)
    headings = [point_heading(first, second) for first, second in zip(coordinates, coordinates[1:])]
    return max(
        (abs(signed_angle_delta(first, second)) for first, second in zip(headings, headings[1:])),
        default=0.0,
    )


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
        col_f = (x - self.xll) / self.cell
        row_f = (self.world_height - (z - self.yll)) / self.cell
        col_f = max(0.0, min(self.ncols - 1.0, col_f))
        row_f = max(0.0, min(self.nrows - 1.0, row_f))
        col0 = int(math.floor(col_f))
        row0 = int(math.floor(row_f))
        col1 = min(self.ncols - 1, col0 + 1)
        row1 = min(self.nrows - 1, row0 + 1)
        col_mix = col_f - col0
        row_mix = row_f - row0
        top = self.values[row0, col0] * (1.0 - col_mix) + self.values[row0, col1] * col_mix
        bottom = self.values[row1, col0] * (1.0 - col_mix) + self.values[row1, col1] * col_mix
        return float(top * (1.0 - row_mix) + bottom * row_mix)


def road_object(model, x, y, z, yaw, pitch):
    return {
        "name": model,
        "pos": [round(x, 3), round(y + ROAD_PLACEMENT_OFFSET, 3), round(z, 3)],
        "ypr": [round(yaw % 360.0, 3), round(pitch, 3), 0.0],
        "scale": 1.0,
        "enableCEPersistency": False,
        "terrainConform": False,
    }


def angular_distance_axis(first, second):
    difference = abs((first % 180.0) - (second % 180.0))
    return min(difference, 180.0 - difference)


def base_family_model(model):
    for base_model in ROAD_MODEL_VARIANTS:
        family_stem = base_model.rsplit("_", 1)[0]
        if model.startswith(family_stem):
            return base_model
    raise KeyError(f"Unknown Michigan road model family: {model}")


def curve_model(base_model, signed_curvature, panel_size):
    if abs(signed_curvature) < CURVATURE_LIMITS[panel_size]:
        return ROAD_MODEL_VARIANTS[base_model][panel_size]
    angle = min(CURVE_ANGLES, key=lambda candidate: abs(abs(signed_curvature) - candidate))
    direction = "R" if signed_curvature > 0.0 else "L"
    family_stem = base_model.rsplit("_", 1)[0]
    return f"{family_stem}_{panel_size}_Curve_{direction}{angle:02d}"


class RoadDeduplicator:
    def __init__(self, cell_size=8.0, profile="legacy"):
        self.cell_size = cell_size
        self.profile = profile
        self.buckets = defaultdict(list)
        self.merged = 0
        self.merged_by_scope = Counter()

    def _cell(self, x, z):
        return int(math.floor(x / self.cell_size)), int(math.floor(z / self.cell_size))

    def add(self, objects, model, measurement):
        center = measurement["center"]
        source_key = measurement.get("source_key")
        road_key = measurement.get("road_key")
        # Curved meshes are not invariant under a 180-degree rotation: an R arc
        # rotated by 180 degrees occupies the L arc's footprint. Keep the full
        # travel heading for placement while still comparing road axes below.
        yaw = measurement["yaw"] % 360.0
        cell_x, cell_z = self._cell(center.x, center.y)
        if self.profile != "off":
            for nearby_x in range(cell_x - 1, cell_x + 2):
                for nearby_z in range(cell_z - 1, cell_z + 2):
                    for entry in self.buckets.get((nearby_x, nearby_z), []):
                        if source_key is not None and entry["source_key"] == source_key:
                            continue
                        both_statewide = (
                            source_key is not None
                            and source_key.startswith("statewide:")
                            and entry["source_key"] is not None
                            and entry["source_key"].startswith("statewide:")
                        )
                        if (
                            base_family_model(entry["model"]) != base_family_model(model)
                            and not both_statewide
                        ):
                            continue
                        same_road = road_key is not None and entry["road_key"] == road_key
                        both_hometown = (
                            source_key is not None
                            and source_key.startswith("hometown:")
                            and entry["source_key"] is not None
                            and entry["source_key"].startswith("hometown:")
                        )
                        if self.profile == "conservative" and both_hometown:
                            continue
                        angle_limit = (
                            SAME_ROAD_DEDUPLICATION_ANGLE if same_road else DEDUPLICATION_ANGLE
                        )
                        longitudinal_limit = (
                            SAME_ROAD_DEDUPLICATION_LONGITUDINAL
                            if same_road
                            else DEDUPLICATION_LONGITUDINAL
                        )
                        lateral_limit = DEDUPLICATION_LATERAL[base_family_model(model)]
                        if both_statewide:
                            lateral_limit = max(
                                lateral_limit,
                                DEDUPLICATION_LATERAL[base_family_model(entry["model"])],
                            )
                        if same_road:
                            lateral_limit *= SAME_ROAD_LATERAL_MULTIPLIER
                        if angular_distance_axis(yaw, entry["yaw"]) > angle_limit:
                            continue
                        delta_x = center.x - entry["x"]
                        delta_z = center.y - entry["z"]
                        heading = math.radians(entry["yaw"])
                        forward_x = math.sin(heading)
                        forward_z = math.cos(heading)
                        right_x = math.cos(heading)
                        right_z = -math.sin(heading)
                        longitudinal = abs(delta_x * forward_x + delta_z * forward_z)
                        lateral = abs(delta_x * right_x + delta_z * right_z)
                        if longitudinal > longitudinal_limit or lateral > lateral_limit:
                            continue

                        item = entry["object"]
                        if source_key is not None and source_key.startswith("hometown:"):
                            item["terrainConform"] = True
                        scope = "hometown" if both_hometown else "statewide_or_cross_scope"
                        self.merged_by_scope[scope] += 1
                        self.merged += 1
                        return False

        item = road_object(
            model,
            center.x,
            measurement["center_height"],
            center.y,
            yaw,
            measurement["pitch"],
        )
        objects.append(item)
        item["terrainConform"] = source_key is not None and source_key.startswith("hometown:")
        if source_key is not None:
            item["_chainId"] = source_key
            item["_roadKey"] = road_key
            item["_chainIndex"] = int(measurement["chain_index"])
            item["_chainDistance"] = round(float(measurement["chain_distance"]), 6)
            item["_panelLength"] = round(float(measurement["panel_length"]), 6)
        self.buckets[(cell_x, cell_z)].append(
            {
                "model": model,
                "x": center.x,
                "z": center.y,
                "height": measurement["center_height"],
                "yaw": yaw,
                "source_key": source_key,
                "road_key": road_key,
                "count": 1,
                "object": item,
            }
        )
        return True


def interpolate_extended(line, distance):
    if 0.0 <= distance <= line.length:
        return line.interpolate(distance)

    tangent_sample = min(SOURCE_SAMPLE_INTERVAL, line.length)
    if distance < 0.0:
        endpoint = line.interpolate(0.0)
        neighbor = line.interpolate(tangent_sample)
        extension = distance
        dx = neighbor.x - endpoint.x
        dz = neighbor.y - endpoint.y
    else:
        endpoint = line.interpolate(line.length)
        neighbor = line.interpolate(line.length - tangent_sample)
        extension = distance - line.length
        dx = endpoint.x - neighbor.x
        dz = endpoint.y - neighbor.y
    magnitude = math.hypot(dx, dz)
    if magnitude < 0.001:
        return endpoint
    return Point(endpoint.x + dx / magnitude * extension, endpoint.y + dz / magnitude * extension)


def measure_panel(line, distance, panel_size, heights, reject_water=True):
    panel_length = PANEL_LENGTHS[panel_size]
    samples = []
    for fraction in (-0.5, -0.25, 0.0, 0.25, 0.5):
        sample_distance = distance + panel_length * fraction
        point = interpolate_extended(line, sample_distance)
        samples.append((sample_distance - distance, point, heights.sample(point.x, point.y)))

    before = samples[0][1]
    middle = samples[2][1]
    after = samples[-1][1]
    dx = after.x - before.x
    dz = after.y - before.y
    if abs(dx) + abs(dz) < 0.001:
        return None, False
    if reject_water and min(sample[2] for sample in samples) < 0.0:
        return None, True

    offsets = [sample[0] for sample in samples]
    sample_heights = [sample[2] for sample in samples]
    offset_mean = sum(offsets) / len(offsets)
    height_mean = sum(sample_heights) / len(sample_heights)
    slope_denominator = sum((offset - offset_mean) ** 2 for offset in offsets)
    if slope_denominator > 0.001:
        slope = sum(
            (offset - offset_mean) * (height - height_mean)
            for offset, height in zip(offsets, sample_heights)
        ) / slope_denominator
    else:
        slope = 0.0

    yaw = math.degrees(math.atan2(dx, dz))
    before_dx = middle.x - before.x
    before_dz = middle.y - before.y
    after_dx = after.x - middle.x
    after_dz = after.y - middle.y
    if abs(before_dx) + abs(before_dz) > 0.001 and abs(after_dx) + abs(after_dz) > 0.001:
        before_heading = math.degrees(math.atan2(before_dx, before_dz))
        after_heading = math.degrees(math.atan2(after_dx, after_dz))
        signed_curvature = ((after_heading - before_heading + 180.0) % 360.0) - 180.0
        curvature = abs(signed_curvature)
    else:
        signed_curvature = 0.0
        curvature = 0.0
    pitch = max(-12.0, min(12.0, math.degrees(math.atan(slope))))
    roughness = max(
        abs(height - (height_mean + slope * (offset - offset_mean)))
        for offset, height in zip(offsets, sample_heights)
    )
    center = samples[2][1]
    center_height = samples[2][2]
    chord_center = Point(
        (before.x + after.x) * 0.5,
        (before.y + after.y) * 0.5,
    )
    return {
        "center": center,
        "chord_center": chord_center,
        "center_height": center_height,
        "yaw": yaw,
        "pitch": pitch,
        "roughness": roughness,
        "curvature": curvature,
        "signed_curvature": signed_curvature,
    }, False


def measure_footprint_roughness(measurement, panel_size, base_model, heights):
    center = measurement["center"]
    heading = math.radians(measurement["yaw"])
    forward_x = math.sin(heading)
    forward_z = math.cos(heading)
    right_x = math.cos(heading)
    right_z = -math.sin(heading)
    half_length = PANEL_LENGTHS[panel_size] * 0.5
    half_width = ROAD_HALF_WIDTHS[base_model]
    samples = []
    for forward_step in range(-2, 3):
        forward_offset = half_length * forward_step * 0.5
        for right_step in range(-2, 3):
            right_offset = half_width * right_step * 0.5
            sample_y = heights.sample(
                center.x + forward_x * forward_offset + right_x * right_offset,
                center.y + forward_z * forward_offset + right_z * right_offset,
            )
            samples.append((forward_offset, right_offset, sample_y))

    sum_forward_squared = sum(forward * forward for forward, _, _ in samples)
    sum_right_squared = sum(right * right for _, right, _ in samples)
    forward_slope = sum(forward * height for forward, _, height in samples) / sum_forward_squared
    right_slope = sum(right * height for _, right, height in samples) / sum_right_squared
    forward_slope = max(-math.tan(math.radians(12.0)), min(math.tan(math.radians(12.0)), forward_slope))
    right_slope = max(-math.tan(math.radians(8.0)), min(math.tan(math.radians(8.0)), right_slope))
    center_height = heights.sample(center.x, center.y)
    return max(
        abs(center_height + forward_slope * forward + right_slope * right - height)
        for forward, right, height in samples
    )


def append_panel(objects, deduplicator, base_model, panel_size, measurement):
    model = ROAD_MODEL_VARIANTS[base_model][panel_size]
    deduplicator.add(objects, model, measurement)


def append_curve_panel(objects, deduplicator, base_model, panel_size, measurement):
    model = curve_model(base_model, measurement["signed_curvature"], panel_size)
    placement = measurement.copy()
    sagitta = 0.0
    if "_Curve_" in model:
        angle = min(
            CURVE_ANGLES,
            key=lambda candidate: abs(abs(measurement["signed_curvature"]) - candidate),
        )
        sign = 1.0 if measurement["signed_curvature"] > 0.0 else -1.0
        panel_length = PANEL_LENGTHS[panel_size]
        curvature = sign * math.radians(angle) / panel_length
        half_angle = curvature * panel_length * 0.5
        sagitta = (1.0 - math.cos(half_angle)) / curvature

    chord_center = measurement["chord_center"]
    heading = math.radians(measurement["yaw"])
    placement["center"] = Point(
        chord_center.x - sagitta * math.cos(heading),
        chord_center.y + sagitta * math.sin(heading),
    )
    deduplicator.add(objects, model, placement)


def line_panels(
    line,
    model,
    heights,
    deduplicator,
    limit,
    source_key=None,
    road_key=None,
    minimum_length=8.0,
    skip_water=True,
):
    objects = []
    skipped_water = 0
    if line.length < minimum_length or limit <= 0:
        return objects, skipped_water
    base_length = PANEL_LENGTHS[6]
    cell_count = max(1, int(math.ceil(line.length / base_length)))
    coverage = cell_count * base_length
    start_offset = (line.length - coverage) * 0.5

    cell_index = 0
    panel_index = 0
    while cell_index < cell_count and len(objects) < limit:
        chosen = None
        base_cell_water = False
        for panel_size in PANEL_SELECTION_ORDER:
            panel_cells = PANEL_CELLS[panel_size]
            if cell_index + panel_cells > cell_count:
                continue
            distance = start_offset + (cell_index + panel_cells * 0.5) * base_length
            measurement, water = measure_panel(
                line,
                distance,
                panel_size,
                heights,
                reject_water=skip_water,
            )
            if water:
                if panel_size == 6:
                    base_cell_water = True
                continue
            if not measurement:
                continue
            if panel_size == 25 and measurement["roughness"] > ROUGHNESS_LIMITS[25]:
                continue
            if panel_size == 12 and measurement["roughness"] > ROUGHNESS_LIMITS[12]:
                continue
            if (
                panel_size != 6
                and source_key is not None
                and source_key.startswith(("hometown:", "mapwide:"))
            ):
                footprint_roughness = measure_footprint_roughness(
                    measurement,
                    panel_size,
                    model,
                    heights,
                )
                if footprint_roughness > FOOTPRINT_ROUGHNESS_LIMITS[panel_size]:
                    continue
                measurement["footprint_roughness"] = footprint_roughness
            if panel_size != 6 and measurement["curvature"] > MAX_LONG_MODULE_CURVATURE:
                continue
            chosen = panel_size, panel_cells, measurement
            break

        if chosen is None:
            if base_cell_water:
                skipped_water += 1
            cell_index += 1
            continue

        panel_size, panel_cells, measurement = chosen
        measurement["source_key"] = source_key
        measurement["road_key"] = road_key
        measurement["chain_index"] = panel_index
        measurement["chain_distance"] = distance
        measurement["panel_length"] = PANEL_LENGTHS[panel_size]
        append_curve_panel(objects, deduplicator, model, panel_size, measurement)
        cell_index += panel_cells
        panel_index += 1
    return objects, skipped_water


def generate_hometown(groups, heights, deduplicator, limit):
    global SKIPPED_SHORT_ACUTE_COUNT
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
        lines = merged_lines(
            source_lines,
            name != "unnamed",
            HOMETOWN_SOURCE_SMOOTH_WINDOW,
            HOMETOWN_SOURCE_SMOOTH_MAX_DEVIATION,
        )
        for line_index, line in enumerate(lines):
            if name == "unnamed" and line.length < 30.0 and maximum_vertex_turn(line) > 60.0:
                SKIPPED_SHORT_ACUTE_COUNT += 1
                continue
            source_key = f"hometown:{name}:{highway}:{line_index}"
            created, skipped = line_panels(
                line,
                model,
                heights,
                deduplicator,
                limit - len(objects),
                source_key,
                f"hometown:{name}:{highway}",
            )
            objects.extend(created)
            skipped_water += skipped
            if len(objects) >= limit:
                return objects, skipped_water
    return objects, skipped_water


def generate_statewide(routes, route_order, heights, deduplicator, limit):
    objects = []
    skipped_water = 0
    route_counts = {}
    for route in route_order:
        route_start = len(objects)
        model = statewide_road_model(route)
        smooth_window, smooth_maximum_deviation = statewide_smoothing(route)
        for line_index, line in enumerate(
            merged_lines(
                routes.get(route, []),
                smooth_window=smooth_window,
                smooth_maximum_deviation=smooth_maximum_deviation,
                loop_maximum_path_distance=STATEWIDE_LOOP_MAX_PATH_DISTANCE,
                loop_closure_distance=STATEWIDE_LOOP_CLOSURE_DISTANCE,
                reject_closed_fragment_loops=True,
            )
        ):
            source_key = f"statewide:{route}:{line_index}"
            created, skipped = line_panels(
                line,
                model,
                heights,
                deduplicator,
                limit - len(objects),
                source_key,
                f"statewide:{route}",
            )
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
        if "Freeway" in item["name"]:
            color = (255, 190, 45)
        elif "4Lane" in item["name"]:
            color = (255, 235, 110)
        elif "3Lane" in item["name"]:
            color = (220, 220, 220)
        else:
            color = (245, 245, 245)
        draw.point((x, y), fill=color)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main():
    global FRAGMENT_JOIN_COUNT, PANEL_SELECTION_ORDER, PRUNED_SHORT_BRANCH_COUNT, REMOVED_SHORT_LOOP_COUNT, SKIPPED_SHORT_ACUTE_COUNT
    FRAGMENT_JOIN_COUNT = 0
    PRUNED_SHORT_BRANCH_COUNT = 0
    REMOVED_SHORT_LOOP_COUNT = 0
    SKIPPED_SHORT_ACUTE_COUNT = 0
    parser = argparse.ArgumentParser(description="Generate a roads-only MichiganMitten mission object layer.")
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA))
    parser.add_argument("--major-roads", default=str(DEFAULT_MAJOR_ROADS))
    parser.add_argument("--hometown-roads", default=str(DEFAULT_HOMETOWN_ROADS))
    parser.add_argument("--heightmap", default=str(DEFAULT_HEIGHTMAP))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--preview", default=str(DEFAULT_PREVIEW))
    parser.add_argument("--routes", default=",".join(DEFAULT_STATEWIDE_ROUTES))
    parser.add_argument("--max-statewide", type=int, default=30000)
    parser.add_argument("--max-hometown", type=int, default=6000)
    parser.add_argument("--panel-sizes", default="25,12,6")
    parser.add_argument(
        "--statewide-carriageway-mode",
        choices=("single-direction", "all"),
        default="single-direction",
    )
    parser.add_argument(
        "--deduplication-profile",
        choices=("legacy", "conservative", "off"),
        default="conservative",
    )
    args = parser.parse_args()

    panel_sizes = tuple(int(value.strip()) for value in args.panel_sizes.split(",") if value.strip())
    if not panel_sizes or any(value not in PANEL_LENGTHS for value in panel_sizes):
        raise ValueError("--panel-sizes must contain only 25, 12, and 6")
    if len(panel_sizes) != len(set(panel_sizes)):
        raise ValueError("--panel-sizes must not contain duplicates")
    PANEL_SELECTION_ORDER = panel_sizes

    route_order = [route.strip().upper().replace("-", " ") for route in args.routes.split(",") if route.strip()]
    metadata = read_json(args.metadata)
    heights = HeightSampler(args.heightmap)
    routes, source_route_counts, corridor_report = load_selected_major(
        args.major_roads,
        route_order,
        args.statewide_carriageway_mode,
    )
    hometown_groups = load_hometown(args.hometown_roads)
    deduplicator = RoadDeduplicator(profile=args.deduplication_profile)

    hometown_objects, hometown_water = generate_hometown(
        hometown_groups,
        heights,
        deduplicator,
        args.max_hometown,
    )
    statewide_objects, statewide_water, route_object_counts = generate_statewide(
        routes,
        route_order,
        heights,
        deduplicator,
        args.max_statewide,
    )
    objects = hometown_objects + statewide_objects
    model_counts = Counter(item["name"] for item in objects)

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
        "statewideCarriageways": {
            "mode": args.statewide_carriageway_mode,
            "routes": corridor_report,
        },
        "routeObjectCounts": route_object_counts,
        "models": {
            "localTwoLane": ROAD_LOCAL_2LANE,
            "ruralTwoLane": ROAD_RURAL_2LANE,
            "urbanThreeLane": ROAD_URBAN_3LANE,
            "urbanFourLane": ROAD_URBAN_4LANE,
            "dividedFreeway": ROAD_FREEWAY_4LANE,
        },
        "modelCounts": dict(sorted(model_counts.items())),
        "panelLengthsMeters": PANEL_LENGTHS,
        "panelSelectionOrder": PANEL_SELECTION_ORDER,
        "roughnessLimitsMeters": ROUGHNESS_LIMITS,
        "curvatureLimitsDegrees": CURVATURE_LIMITS,
        "curveAnglesDegrees": CURVE_ANGLES,
        "placementOffsetMeters": ROAD_PLACEMENT_OFFSET,
        "panelSpacingMeters": PANEL_LENGTHS[6],
        "sourceSmoothing": {
            "sampleIntervalMeters": SOURCE_SAMPLE_INTERVAL,
            "windowMeters": SOURCE_SMOOTH_WINDOW,
            "maximumDeviationMeters": SOURCE_SMOOTH_MAX_DEVIATION,
            "hometownWindowMeters": HOMETOWN_SOURCE_SMOOTH_WINDOW,
            "hometownMaximumDeviationMeters": HOMETOWN_SOURCE_SMOOTH_MAX_DEVIATION,
            "fragmentJoinMaxGapMeters": FRAGMENT_JOIN_MAX_GAP,
            "fragmentJoinMaxAngleDegrees": FRAGMENT_JOIN_MAX_ANGLE,
            "fragmentJoins": FRAGMENT_JOIN_COUNT,
            "prunedShortParallelBranches": PRUNED_SHORT_BRANCH_COUNT,
            "removedShortLoops": REMOVED_SHORT_LOOP_COUNT,
            "skippedShortAcuteFragments": SKIPPED_SHORT_ACUTE_COUNT,
        },
        "curvePanels": sum(1 for item in objects if "_Curve_" in item["name"]),
        "deduplication": {
            "profile": args.deduplication_profile,
            "mergedPanels": deduplicator.merged,
            "mergedByScope": dict(sorted(deduplicator.merged_by_scope.items())),
            "longitudinalMeters": DEDUPLICATION_LONGITUDINAL,
            "lateralMeters": {key: value for key, value in DEDUPLICATION_LATERAL.items()},
            "angleDegrees": DEDUPLICATION_ANGLE,
            "sameRoadLongitudinalMeters": SAME_ROAD_DEDUPLICATION_LONGITUDINAL,
            "sameRoadAngleDegrees": SAME_ROAD_DEDUPLICATION_ANGLE,
            "sameRoadLateralMultiplier": SAME_ROAD_LATERAL_MULTIPLIER,
        },
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
    print(f"Model counts: {dict(sorted(model_counts.items()))}")
    print(f"Skipped over water: {hometown_water + statewide_water}")


if __name__ == "__main__":
    main()
