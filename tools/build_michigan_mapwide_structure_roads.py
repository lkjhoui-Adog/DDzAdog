#!/usr/bin/env python3
"""Build one building-aware paved and dirt road network for Michigan Mitten."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from shapely import union_all
from shapely.geometry import LineString, MultiLineString, Point, mapping, shape
from shapely.ops import nearest_points
from shapely.prepared import prep
from shapely.strtree import STRtree

from expand_michigan_city_districts import (
    add_hometown_features,
    city_centers,
    expansion_radii,
    geometry_lines,
    group_source_features,
    load_document,
    load_land,
    scaled_candidates,
)


ROOT = Path(__file__).resolve().parents[1]
EXPORT_ROOT = ROOT / "terrain" / "exports" / "michigan-lower-peninsula"
DEFAULT_EXISTING = (
    ROOT
    / "build"
    / "candidates"
    / "bridge-road-parity-20260716-pass6-wrp-route-isolated"
    / "physical-road-map-network-repaired-world.geojson"
)
DEFAULT_FOOTPRINTS = (
    ROOT
    / "build"
    / "candidates"
    / "road-aligned-city-population-20260716-pass13-statewide-complete"
    / "michigan-road-aligned-building-footprints.geojson"
)
DEFAULT_SPECIAL_SITES = (
    ROOT
    / "build"
    / "candidates"
    / "michigan-special-sites-20260716-pass7-audited"
    / "michigan-special-sites-world.geojson"
)
DEFAULT_RAW_CITY = EXPORT_ROOT / "vectors" / "city_roads_world.geojson"
DEFAULT_HOMETOWN = EXPORT_ROOT / "vectors" / "hometown_roads_world.geojson"
DEFAULT_LAND = EXPORT_ROOT / "vectors" / "mitten_mainland_world.geojson"
DEFAULT_LANDMARKS = EXPORT_ROOT / "terrain_builder_export_metadata.json"
DEFAULT_OUTPUT = ROOT / "build" / "diagnostics" / "michigan-mapwide-structure-roads.geojson"
DEFAULT_REPORT = ROOT / "build" / "diagnostics" / "michigan-mapwide-structure-roads-report.json"
DEFAULT_PREVIEW = ROOT / "build" / "diagnostics" / "michigan-mapwide-structure-roads-preview.png"

WORLD_SIZE = 40960.0
MASK_SIZE = 4096
ROAD_HALF_WIDTH = {
    "MI_Road_Dirt_2Lane": 3.0,
    "MI_Road_Local_2Lane": 3.3,
    "MI_Road_Rural_2Lane": 3.8,
    "MI_Road_Urban_3Lane": 5.6,
    "MI_Road_Urban_4Lane": 7.6,
    "MI_Road_Freeway_4Lane": 9.5,
}
CITY_ADDITION_CAP = {
    "metro": 420,
    "regional": 240,
    "town": 150,
    "hometown": 260,
}
CITY_CLEARANCE = 1.8
DIRT_CLEARANCE = 1.5


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def model_family(properties: dict) -> str:
    model = str(properties.get("model") or "")
    for family in ROAD_HALF_WIDTH:
        if model.startswith(family):
            return family
    highway = str(properties.get("highway") or "")
    surface = str(properties.get("surface") or "")
    if surface == "dirt":
        return "MI_Road_Dirt_2Lane"
    if highway in {"motorway", "trunk"}:
        return "MI_Road_Freeway_4Lane"
    if highway in {"primary", "secondary"}:
        return "MI_Road_Urban_3Lane"
    return "MI_Road_Local_2Lane"


def line_parts(geometry) -> list[LineString]:
    if isinstance(geometry, LineString):
        return [geometry]
    if isinstance(geometry, MultiLineString):
        return list(geometry.geoms)
    return []


def safe_parts(line: LineString, obstacle_union, half_width: float, clearance: float) -> list[LineString]:
    if obstacle_union.is_empty:
        return [line]
    forbidden = obstacle_union.buffer(half_width + clearance, join_style="mitre")
    return parts_outside(line, forbidden)


def parts_outside(line: LineString, forbidden) -> list[LineString]:
    clipped = line.difference(forbidden)
    return [part for part in line_parts(clipped) if part.length >= 20.0]


def feature(properties: dict, line: LineString) -> dict:
    output_properties = dict(properties)
    output_properties["lengthMeters"] = round(float(line.length), 3)
    return {
        "type": "Feature",
        "properties": output_properties,
        "geometry": mapping(line),
    }


def union_or_empty(geometries: list):
    return union_all(geometries) if geometries else Point(-1000.0, -1000.0).buffer(0.0)


def load_masks() -> dict[str, np.ndarray]:
    masks = {}
    for name in ("farmland", "woods", "urban", "water", "mitten"):
        path = EXPORT_ROOT / "masks" / f"{name}_mask_{MASK_SIZE}.png"
        masks[name] = np.asarray(Image.open(path).convert("L")) > 0
    return masks


def mask_value(mask: np.ndarray, x: float, z: float) -> bool:
    column = int(round(max(0.0, min(WORLD_SIZE, x)) * (MASK_SIZE - 1) / WORLD_SIZE))
    row = int(round((WORLD_SIZE - max(0.0, min(WORLD_SIZE, z))) * (MASK_SIZE - 1) / WORLD_SIZE))
    return bool(mask[row, column])


def split_sampled_line(points: list[tuple[float, float]], valid) -> list[LineString]:
    parts: list[LineString] = []
    current: list[tuple[float, float]] = []
    for point in points:
        if valid(*point):
            current.append(point)
            continue
        if len(current) >= 2:
            parts.append(LineString(current))
        current = []
    if len(current) >= 2:
        parts.append(LineString(current))
    return parts


def sampled_axis_line(axis: str, fixed: float, interval: float = 20.0) -> list[tuple[float, float]]:
    values = np.arange(0.0, WORLD_SIZE + interval, interval)
    if axis == "horizontal":
        return [(float(value), fixed) for value in values]
    return [(fixed, float(value)) for value in values]


def generate_dirt_grid(
    masks: dict[str, np.ndarray],
    obstacles,
    paved_lines: list[LineString],
    spacing: float,
) -> tuple[list[dict], dict]:
    output: list[dict] = []
    rejected = Counter()
    forbidden = obstacles.buffer(ROAD_HALF_WIDTH["MI_Road_Dirt_2Lane"] + DIRT_CLEARANCE)
    paved_tree = STRtree(paved_lines)

    def valid(x: float, z: float) -> bool:
        if not mask_value(masks["mitten"], x, z):
            return False
        if mask_value(masks["water"], x, z) or mask_value(masks["urban"], x, z):
            return False
        if not mask_value(masks["farmland"], x, z):
            return False
        return not forbidden.contains(Point(x, z))

    axis_offsets = (("horizontal", spacing * 0.35), ("vertical", spacing * 0.72))
    for axis, offset in axis_offsets:
        fixed = offset
        ordinal = 0
        while fixed < WORLD_SIZE:
            raw = sampled_axis_line(axis, fixed)
            for sampled_part in split_sampled_line(raw, valid):
                for part in parts_outside(sampled_part, forbidden):
                    if part.length < 260.0:
                        rejected["shortFarmlandRun"] += 1
                        continue
                    nearby_indices = paved_tree.query(part, predicate="dwithin", distance=22.0)
                    close_length = sum(
                        part.intersection(paved_lines[int(index)].buffer(22.0)).length
                        for index in nearby_indices
                    )
                    if close_length > part.length * 0.34:
                        rejected["pavedParallel"] += 1
                        continue
                    properties = {
                        "scope": "farmland-dirt",
                        "surface": "dirt",
                        "model": "MI_Road_Dirt_2Lane",
                        "name": f"Michigan Farm Road {axis[0].upper()}{ordinal:03d}",
                        "condition": "fifteen-year-weathered-rutted-light-overgrowth",
                        "physicalSource": True,
                    }
                    output.append(feature(properties, part))
                    ordinal += 1
            fixed += spacing

    dirt_union = union_or_empty([shape(item["geometry"]) for item in output])
    connectors: list[dict] = []
    for index, item in enumerate(output):
        line = shape(item["geometry"])
        for endpoint_index, coordinate in enumerate((line.coords[0], line.coords[-1])):
            endpoint = Point(coordinate)
            nearest_index = int(paved_tree.nearest(endpoint))
            nearest_paved_line = paved_lines[nearest_index]
            if endpoint.distance(nearest_paved_line) <= 26.0:
                continue
            nearest_dirt, nearest_paved = nearest_points(endpoint, nearest_paved_line)
            distance = nearest_dirt.distance(nearest_paved)
            if distance > 260.0:
                continue
            connector = LineString([nearest_dirt, nearest_paved])
            if connector.length < 20.0 or connector.buffer(4.5).intersects(forbidden):
                continue
            if connector.length and connector.intersection(dirt_union.buffer(8.0)).length > connector.length * 0.7:
                continue
            properties = {
                "scope": "farmland-dirt-connector",
                "surface": "dirt",
                "model": "MI_Road_Dirt_2Lane",
                "name": f"Farm Connector {index:04d}-{endpoint_index}",
                "condition": "fifteen-year-weathered-rutted-light-overgrowth",
                "physicalSource": True,
            }
            connectors.append(feature(properties, connector))
    output.extend(connectors)
    return output, {
        "gridRuns": len(output) - len(connectors),
        "connectors": len(connectors),
        "rejected": dict(rejected),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing", type=Path, default=DEFAULT_EXISTING)
    parser.add_argument("--footprints", type=Path, default=DEFAULT_FOOTPRINTS)
    parser.add_argument("--special-sites", type=Path, default=DEFAULT_SPECIAL_SITES)
    parser.add_argument("--raw-city", type=Path, default=DEFAULT_RAW_CITY)
    parser.add_argument("--hometown", type=Path, default=DEFAULT_HOMETOWN)
    parser.add_argument("--land", type=Path, default=DEFAULT_LAND)
    parser.add_argument("--landmarks", type=Path, default=DEFAULT_LANDMARKS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--preview", type=Path, default=DEFAULT_PREVIEW)
    parser.add_argument("--dirt-spacing", type=float, default=1180.0)
    args = parser.parse_args()

    footprint_document = read_json(args.footprints)
    city_footprints: dict[str, list] = defaultdict(list)
    all_buildings = []
    for item in footprint_document.get("features", []):
        polygon = shape(item["geometry"])
        city_id = str(item.get("properties", {}).get("cityId") or "")
        city_footprints[city_id].append(polygon)
        all_buildings.append(polygon)

    special_document = read_json(args.special_sites)
    for item in special_document.get("features", []):
        if item.get("properties", {}).get("featureType") == "building":
            all_buildings.append(shape(item["geometry"]))
    obstacle_union = union_or_empty(all_buildings)
    forbidden_by_family = {
        family: obstacle_union.buffer(half_width + CITY_CLEARANCE, join_style="mitre")
        for family, half_width in ROAD_HALF_WIDTH.items()
    }
    forbidden_by_family["MI_Road_Dirt_2Lane"] = obstacle_union.buffer(
        ROAD_HALF_WIDTH["MI_Road_Dirt_2Lane"] + DIRT_CLEARANCE,
        join_style="mitre",
    )

    existing_document = read_json(args.existing)
    output_features: list[dict] = []
    paved_lines = []
    existing_counts = Counter()
    for source_index, item in enumerate(existing_document.get("features", [])):
        properties = dict(item.get("properties") or {})
        properties.update({"networkSource": "retained-physical", "sourceFeatureIndex": source_index})
        family = model_family(properties)
        for source_line in geometry_lines(shape(item["geometry"])):
            for line in parts_outside(source_line, forbidden_by_family[family]):
                output_features.append(feature(properties, line))
                if family != "MI_Road_Dirt_2Lane":
                    paved_lines.append(line)
                existing_counts[str(properties.get("cityId") or properties.get("scope") or "statewide")] += 1

    raw_city_document = load_document(args.raw_city)
    add_hometown_features(raw_city_document, args.hometown)
    grouped = group_source_features(raw_city_document)
    centers = city_centers(args.landmarks)
    plans = expansion_radii(grouped, centers)
    land = load_land(args.land)

    existing_by_city: dict[str, list[LineString]] = defaultdict(list)
    for item in output_features:
        city_id = str(item.get("properties", {}).get("cityId") or "")
        if city_id:
            existing_by_city[city_id].append(shape(item["geometry"]))

    city_report = {}
    added_city_features: list[dict] = []
    for city_id in sorted(grouped):
        buildings = city_footprints.get(city_id, [])
        if not buildings or city_id not in centers:
            continue
        building_union = union_all(buildings)
        city_envelope = building_union.convex_hull.buffer(135.0).intersection(land)
        plan = plans[city_id]
        candidates, rejected = scaled_candidates(
            city_id, grouped[city_id], centers[city_id], plan, land
        )
        current_lines = list(existing_by_city.get(city_id, []))
        baseline_union = union_or_empty(current_lines)
        baseline_road_buffer = baseline_union.buffer(7.0)
        cap = CITY_ADDITION_CAP[plan["tier"]]
        accepted = []
        rejected_counts = Counter(rejected)
        ordered = sorted(
            candidates,
            key=lambda item: (
                0 if item["named"] else 1,
                0 if item["highway"] in {"tertiary", "unclassified"} else 1,
                item["geometry"].distance(building_union),
                item["distance"],
            ),
        )
        for candidate in ordered:
            if len(accepted) >= cap:
                rejected_counts["cityCap"] += 1
                continue
            line = candidate["geometry"].intersection(city_envelope)
            parts = [part for part in line_parts(line) if part.length >= 28.0]
            for part in parts:
                if len(accepted) >= cap:
                    break
                if part.distance(building_union) > 125.0:
                    rejected_counts["outsideOccupiedBlocks"] += 1
                    continue
                candidate_family = (
                    "MI_Road_Urban_3Lane"
                    if candidate["highway"] == "tertiary"
                    else "MI_Road_Local_2Lane"
                )
                safe = parts_outside(part, forbidden_by_family[candidate_family])
                for safe_line in safe:
                    if len(accepted) >= cap:
                        break
                    overlap = safe_line.intersection(baseline_road_buffer).length
                    if overlap > safe_line.length * 0.58:
                        rejected_counts["duplicateExisting"] += 1
                        continue
                    if safe_line.distance(baseline_union) > 55.0:
                        rejected_counts["disconnected"] += 1
                        continue
                    properties = {
                        "scope": "city-structure-fill",
                        "networkSource": "scaled-real-michigan-street",
                        "physicalSource": True,
                        "cityId": city_id,
                        "cityName": grouped[city_id]["properties"].get("cityName", city_id),
                        "cityTier": plan["tier"],
                        "districtZone": candidate["zone"],
                        "highway": candidate["highway"],
                        "name": candidate["name"],
                        "model": candidate_family,
                        "condition": "fifteen-year-weathered-light-cracking-and-patching",
                    }
                    accepted_feature = feature(properties, safe_line)
                    accepted.append(accepted_feature)
                    current_lines.append(safe_line)
        added_city_features.extend(accepted)
        current_union = union_or_empty(current_lines)
        frontage = sum(1 for polygon in buildings if polygon.distance(current_union) <= 28.0)
        city_report[city_id] = {
            "tier": plan["tier"],
            "buildingCount": len(buildings),
            "retainedRoadFeatures": len(existing_by_city.get(city_id, [])),
            "addedRoadFeatures": len(accepted),
            "buildingsWithRoadWithin28m": frontage,
            "frontagePercent": round(frontage * 100.0 / len(buildings), 2),
            "rejected": dict(rejected_counts),
        }
        print(
            f"{city_id}: retained {len(existing_by_city.get(city_id, []))}, "
            f"added {len(accepted)}, frontage {frontage}/{len(buildings)}",
            flush=True,
        )
    output_features.extend(added_city_features)
    paved_lines.extend(shape(item["geometry"]) for item in added_city_features)

    special_access_count = 0
    for item in special_document.get("features", []):
        properties = dict(item.get("properties") or {})
        if properties.get("featureType") != "access-route":
            continue
        surface = "dirt" if properties.get("surface") == "dirt" else "weathered-asphalt"
        family = "MI_Road_Dirt_2Lane" if surface == "dirt" else "MI_Road_Local_2Lane"
        properties.update(
            {
                "scope": "special-site-access",
                "surface": surface,
                "model": family,
                "physicalSource": True,
                "networkSource": "special-site-plan",
            }
        )
        for source_line in geometry_lines(shape(item["geometry"])):
            for line in parts_outside(source_line, forbidden_by_family[family]):
                output_features.append(feature(properties, line))
                if surface != "dirt":
                    paved_lines.append(line)
                special_access_count += 1

    dirt_features, dirt_report = generate_dirt_grid(
        load_masks(), obstacle_union, paved_lines, args.dirt_spacing
    )
    output_features.extend(dirt_features)

    road_geometries = [shape(item["geometry"]) for item in output_features]
    surface_conflicts = 0
    prepared_forbidden = {
        family: prep(geometry) for family, geometry in forbidden_by_family.items()
    }
    for item, line in zip(output_features, road_geometries):
        family = model_family(item["properties"])
        if (
            prepared_forbidden[family].intersects(line)
            and line.intersection(forbidden_by_family[family]).length > 0.02
        ):
            surface_conflicts += 1
    if surface_conflicts:
        raise RuntimeError(f"Final network still has {surface_conflicts} building surface conflicts")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"type": "FeatureCollection", "features": output_features}, separators=(",", ":")),
        encoding="ascii",
    )

    preview_size = 2048
    preview = Image.new("RGB", (preview_size, preview_size), (220, 226, 215))
    draw = ImageDraw.Draw(preview)
    for item in output_features:
        properties = item["properties"]
        family = model_family(properties)
        color = (151, 112, 63) if family == "MI_Road_Dirt_2Lane" else (235, 221, 157)
        width = 1 if family == "MI_Road_Dirt_2Lane" else 2
        for line in geometry_lines(shape(item["geometry"])):
            points = [
                (
                    round(x * (preview_size - 1) / WORLD_SIZE),
                    round((WORLD_SIZE - z) * (preview_size - 1) / WORLD_SIZE),
                )
                for x, z in line.coords
            ]
            draw.line(points, fill=color, width=width, joint="curve")
    for polygon in all_buildings:
        center = polygon.centroid
        x = round(center.x * (preview_size - 1) / WORLD_SIZE)
        y = round((WORLD_SIZE - center.y) * (preview_size - 1) / WORLD_SIZE)
        draw.point((x, y), fill=(94, 49, 44))
    args.preview.parent.mkdir(parents=True, exist_ok=True)
    preview.save(args.preview, optimize=True)

    scope_counts = Counter(str(item["properties"].get("scope") or "unknown") for item in output_features)
    dirt_length = sum(
        shape(item["geometry"]).length
        for item in output_features
        if model_family(item["properties"]) == "MI_Road_Dirt_2Lane"
    )
    report = {
        "output": str(args.output.resolve()),
        "preview": str(args.preview.resolve()),
        "sourceExistingFeatures": len(existing_document.get("features", [])),
        "outputFeatures": len(output_features),
        "outputLengthKilometers": round(sum(line.length for line in road_geometries) / 1000.0, 3),
        "addedCityFeatures": len(added_city_features),
        "dirtFeatures": len(dirt_features),
        "dirtLengthKilometers": round(dirt_length / 1000.0, 3),
        "specialAccessFeatures": special_access_count,
        "buildingFootprints": len(all_buildings),
        "roadSurfaceBuildingConflicts": surface_conflicts,
        "scopeCounts": dict(scope_counts),
        "dirt": dirt_report,
        "cities": city_report,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
