#!/usr/bin/env python3
"""Materialize building-aware city and dirt roads into a settled Michigan WRP."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from shapely import union_all
from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely.ops import nearest_points
from shapely.strtree import STRtree

from embed_michigan_roads_in_wrp import (
    HeightGrid,
    arc_point,
    evaluate_fixed_placement,
    fit_road_to_terrain,
    locate_object_section_without_empty_requirement,
    parse_embedded_objects,
    road_dimensions,
)
from generate_michigan_mitten_roads import (
    ROAD_DIRT_2LANE,
    ROAD_LOCAL_2LANE,
    ROAD_URBAN_3LANE,
    RoadDeduplicator,
    angular_distance_axis,
    base_family_model,
    line_panels,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WRP = (
    ROOT
    / "build"
    / "candidates"
    / "michigan-special-sites-20260716-pass7-audited"
    / "integration"
    / "MichiganMitten-install-source.wrp"
)
DEFAULT_NETWORK = (
    ROOT
    / "build"
    / "candidates"
    / "mapwide-structure-roads-20260717-pass2"
    / "michigan-mapwide-structure-roads.geojson"
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
DEFAULT_OUTPUT_ROOT = ROOT / "build" / "candidates" / "mapwide-structure-roads-20260717-pass3-physical"

ROAD_PREFIX = "michiganmitten_roads\\models\\roads\\"
FAMILY_PATHS = {
    "mi_local_2lane": "MI_Road_Local_2Lane",
    "mi_rural_2lane": "MI_Road_Rural_2Lane",
    "mi_urban_3lane": "MI_Road_Urban_3Lane",
    "mi_urban_4lane": "MI_Road_Urban_4Lane",
    "mi_freeway_4lane": "MI_Road_Freeway_4Lane",
    "mi_dirt_2lane": "MI_Road_Dirt_2Lane",
}
TARGET_SCOPES = {
    "city-structure-fill",
    "city-frontage-connector",
    "farmland-dirt",
    "farmland-dirt-connector",
}
BASE_MODELS = {
    "MI_Road_Local_2Lane": ROAD_LOCAL_2LANE,
    "MI_Road_Urban_3Lane": ROAD_URBAN_3LANE,
    "MI_Road_Dirt_2Lane": ROAD_DIRT_2LANE,
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def class_from_path(path: str) -> str | None:
    lower = str(path).replace("/", "\\").lower()
    if not lower.startswith(ROAD_PREFIX):
        return None
    stem = Path(lower.replace("\\", "/")).stem
    for prefix, family in FAMILY_PATHS.items():
        if stem.startswith(prefix):
            return family + stem[len(prefix) :]
    return None


def class_family(class_name: str) -> str:
    for family in FAMILY_PATHS.values():
        if class_name.startswith(family):
            return family
    raise ValueError(f"Unknown Michigan road family: {class_name}")


def yaw_from_matrix(matrix) -> float:
    return math.degrees(math.atan2(-float(matrix[2]), float(matrix[0]))) % 360.0


def object_from_record(record: dict, class_name: str, source_ordinal: int) -> dict:
    matrix = [float(value) for value in record["matrix"]]
    return {
        "name": class_name,
        "pos": [matrix[9], matrix[10], matrix[11]],
        "ypr": [yaw_from_matrix(matrix), 0.0, 0.0],
        "scale": 1.0,
        "enableCEPersistency": False,
        "terrainConform": False,
        "_sourceRoadOrdinal": source_ordinal,
    }


def panel_polygon(class_name: str, matrix) -> Polygon:
    half_width, module_length, curvature = road_dimensions(class_name)
    right = np.asarray(matrix[0:3], dtype=np.float64)
    forward = np.asarray(matrix[6:9], dtype=np.float64)
    position = np.asarray(matrix[9:12], dtype=np.float64)
    left = []
    right_edge = []
    for fraction in np.linspace(-0.5, 0.5, 9):
        distance = module_length * float(fraction)
        local_x, local_z = arc_point(distance, -half_width, curvature)
        world = position + right * local_x + forward * local_z
        left.append((float(world[0]), float(world[2])))
        local_x, local_z = arc_point(distance, half_width, curvature)
        world = position + right * local_x + forward * local_z
        right_edge.append((float(world[0]), float(world[2])))
    return Polygon(left + list(reversed(right_edge)))


def placement(index: int, item: dict, matrix, stats: dict | None = None) -> dict:
    output = {
        "index": index,
        "className": item["name"],
        "matrix": [float(value) for value in matrix],
    }
    if stats:
        output.update(stats)
    return output


def lift_matrix_clear_of_terrain(item: dict, matrix: list[float], grid: HeightGrid) -> list[float]:
    adjusted = [float(value) for value in matrix]
    stats = evaluate_fixed_placement(item, adjusted, grid)
    inset = float(stats["terrainInset"])
    if inset > 0.0:
        adjusted[10] += inset + 0.001
    return adjusted


def add_frontage_connectors(network: dict, city_footprints: list[dict]) -> list[dict]:
    added = []
    roads_by_city: dict[str, list[LineString]] = defaultdict(list)
    for item in network.get("features", []):
        city_id = str(item.get("properties", {}).get("cityId") or "")
        if city_id:
            geometry = shape(item["geometry"])
            if isinstance(geometry, LineString):
                roads_by_city[city_id].append(geometry)

    all_polygons = [shape(item["geometry"]) for item in city_footprints]
    for city_id in sorted(roads_by_city):
        city_buildings = [
            (item, shape(item["geometry"]))
            for item in city_footprints
            if str(item.get("properties", {}).get("cityId") or "") == city_id
        ]
        road_lines = roads_by_city[city_id]
        road_tree = STRtree(road_lines)
        for source, polygon in city_buildings:
            nearest_index = int(road_tree.nearest(polygon))
            nearest_road = road_lines[nearest_index]
            if polygon.distance(nearest_road) <= 28.0:
                continue
            road_point, building_point = nearest_points(nearest_road, polygon.buffer(6.0))
            connector = LineString([road_point, building_point])
            if not (8.0 <= connector.length <= 90.0):
                continue
            other_buildings = [candidate for candidate in all_polygons if candidate is not polygon]
            if any(connector.buffer(5.1).intersects(candidate) for candidate in other_buildings):
                continue
            properties = dict(source.get("properties") or {})
            properties.update(
                {
                    "scope": "city-frontage-connector",
                    "networkSource": "building-frontage-repair",
                    "physicalSource": True,
                    "model": "MI_Road_Local_2Lane",
                    "name": f"{city_id} Building Access {properties.get('index', 0)}",
                    "condition": "fifteen-year-weathered-light-cracking-and-patching",
                    "lengthMeters": round(connector.length, 3),
                }
            )
            added.append(
                {"type": "Feature", "properties": properties, "geometry": mapping(connector)}
            )
            road_lines.append(connector)
            road_tree = STRtree(road_lines)
    network["features"].extend(added)
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-wrp", type=Path, default=DEFAULT_WRP)
    parser.add_argument("--network", type=Path, default=DEFAULT_NETWORK)
    parser.add_argument("--footprints", type=Path, default=DEFAULT_FOOTPRINTS)
    parser.add_argument("--special-sites", type=Path, default=DEFAULT_SPECIAL_SITES)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--surface-offset", type=float, default=0.003)
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    output_objects = args.output_root / "MichiganMittenObjects-mapwide-structure-roads.json"
    output_placements = args.output_root / "MichiganMittenPlacements-mapwide-structure-roads.json"
    output_network = args.output_root / "michigan-mapwide-structure-roads-final.geojson"
    output_report = args.output_root / "michigan-mapwide-structure-road-materialization-report.json"

    city_footprint_document = read_json(args.footprints)
    city_footprint_features = list(city_footprint_document.get("features", []))
    building_polygons = [shape(item["geometry"]) for item in city_footprint_features]
    for item in read_json(args.special_sites).get("features", []):
        if item.get("properties", {}).get("featureType") == "building":
            building_polygons.append(shape(item["geometry"]))
    building_tree = STRtree(building_polygons)

    network = read_json(args.network)
    frontage_connectors = add_frontage_connectors(network, city_footprint_features)
    output_network.write_text(json.dumps(network, separators=(",", ":")), encoding="ascii")

    source_blob = args.input_wrp.read_bytes()
    layout, height_values, _ = locate_object_section_without_empty_requirement(source_blob)
    grid = HeightGrid(height_values, layout.terrain_cell_size)
    embedded = parse_embedded_objects(source_blob, layout)
    road_records = []
    for index, record in enumerate(embedded):
        class_name = class_from_path(record["path"])
        if class_name is not None:
            road_records.append((index, record, class_name))
    if not road_records:
        raise RuntimeError("The source WRP has no Michigan road objects")

    retained_objects = []
    retained_matrices = []
    retained_points = []
    retained_meta = []
    removed_conflicts = []
    reseated_retained = 0
    for source_ordinal, (wrp_index, record, class_name) in enumerate(road_records):
        lower_class = class_name.lower()
        structural = any(
            marker in lower_class
            for marker in ("_support_", "_pier_", "_tower_", "_anchor_", "_cable_")
        )
        locked_structure = structural or "_bridge_" in lower_class or "_landmark_" in lower_class
        conflict_ids = []
        if not structural:
            footprint = panel_polygon(class_name, record["matrix"]).buffer(1.8)
            for candidate_index in building_tree.query(footprint, predicate="intersects"):
                candidate = building_polygons[int(candidate_index)]
                if footprint.intersection(candidate).area > 0.05:
                    conflict_ids.append(int(candidate_index))
        if conflict_ids:
            removed_conflicts.append(
                {
                    "sourceRoadOrdinal": source_ordinal,
                    "wrpObjectIndex": wrp_index,
                    "objectId": int(record["id"]),
                    "className": class_name,
                    "buildingIndices": conflict_ids,
                }
            )
            continue
        item = object_from_record(record, class_name, source_ordinal)
        if locked_structure:
            item["_bridgeSupportFor"] = f"retained-structure-{source_ordinal}"
            retained_matrix = [float(value) for value in record["matrix"]]
        else:
            retained_matrix, _ = fit_road_to_terrain(
                item,
                grid,
                args.surface_offset,
                placement_mode="cover",
            )
            retained_matrix = lift_matrix_clear_of_terrain(item, retained_matrix, grid)
            reseated_retained += 1
        retained_objects.append(item)
        retained_matrices.append(retained_matrix)
        retained_points.append(Point(float(retained_matrix[9]), float(retained_matrix[11])))
        retained_meta.append((class_family(class_name), yaw_from_matrix(retained_matrix)))

    retained_tree = STRtree(retained_points)
    deduplicator = RoadDeduplicator(profile="conservative")
    generated = []
    skipped_water = 0
    scope_counts = Counter()
    for feature_index, source in enumerate(network.get("features", [])):
        properties = dict(source.get("properties") or {})
        scope = str(properties.get("scope") or "")
        if scope not in TARGET_SCOPES:
            continue
        family = str(properties.get("model") or "MI_Road_Local_2Lane")
        base_model = BASE_MODELS.get(family)
        if base_model is None:
            raise ValueError(f"No generator base model for {family}")
        line = shape(source["geometry"])
        if not isinstance(line, LineString):
            continue
        created, water = line_panels(
            line,
            base_model,
            grid,
            deduplicator,
            1_000_000,
            source_key=f"mapwide:{scope}:{feature_index}",
            road_key=str(properties.get("name") or f"feature-{feature_index}"),
            minimum_length=8.0,
            skip_water=True,
        )
        for item in created:
            item["_scope"] = scope
            item["_cityId"] = properties.get("cityId")
        generated.extend(created)
        skipped_water += water
        scope_counts[scope] += len(created)

    new_objects = []
    new_matrices = []
    duplicate_retained = 0
    new_building_conflicts = 0
    for item in generated:
        point = Point(float(item["pos"][0]), float(item["pos"][2]))
        family = class_family(str(item["name"]))
        yaw = float(item["ypr"][0])
        duplicate = False
        for candidate_index in retained_tree.query(point, predicate="dwithin", distance=5.8):
            candidate_family, candidate_yaw = retained_meta[int(candidate_index)]
            if candidate_family != family:
                continue
            if angular_distance_axis(yaw, candidate_yaw) <= 12.0:
                duplicate = True
                break
        if duplicate:
            duplicate_retained += 1
            continue
        matrix, stats = fit_road_to_terrain(
            item,
            grid,
            args.surface_offset,
            placement_mode="cover",
        )
        matrix = lift_matrix_clear_of_terrain(item, matrix, grid)
        stats = evaluate_fixed_placement(item, matrix, grid)
        footprint = panel_polygon(str(item["name"]), matrix).buffer(1.8)
        conflict = any(
            footprint.intersection(building_polygons[int(candidate_index)]).area > 0.05
            for candidate_index in building_tree.query(footprint, predicate="intersects")
        )
        if conflict:
            new_building_conflicts += 1
            continue
        new_objects.append(item)
        new_matrices.append((matrix, stats))

    objects = retained_objects + new_objects
    placements = []
    for index, (item, matrix) in enumerate(zip(retained_objects, retained_matrices)):
        placements.append(placement(index, item, matrix))
    for offset, (item, (matrix, stats)) in enumerate(zip(new_objects, new_matrices)):
        placements.append(placement(len(retained_objects) + offset, item, matrix, stats))

    output_objects.write_text(json.dumps({"Objects": objects}, separators=(",", ":")), encoding="ascii")
    output_placements.write_text(
        json.dumps({"placements": placements}, separators=(",", ":")), encoding="ascii"
    )

    final_frontage = {}
    network_by_city: dict[str, list] = defaultdict(list)
    for item in network.get("features", []):
        city_id = str(item.get("properties", {}).get("cityId") or "")
        if city_id:
            network_by_city[city_id].append(shape(item["geometry"]))
    for city_id, lines in sorted(network_by_city.items()):
        road_union = union_all(lines)
        polygons = [
            shape(item["geometry"])
            for item in city_footprint_features
            if str(item.get("properties", {}).get("cityId") or "") == city_id
        ]
        covered = sum(polygon.distance(road_union) <= 28.0 for polygon in polygons)
        final_frontage[city_id] = {
            "buildings": len(polygons),
            "within28m": covered,
            "percent": round(covered * 100.0 / max(1, len(polygons)), 2),
        }

    report = {
        "inputWrp": str(args.input_wrp.resolve()),
        "sourceNativeObjects": len(embedded),
        "sourceRoadObjects": len(road_records),
        "retainedRoadObjects": len(retained_objects),
        "reseatedRetainedRoadObjects": reseated_retained,
        "removedBuildingConflictRoadObjects": len(removed_conflicts),
        "generatedCandidateRoadObjects": len(generated),
        "deduplicatedAgainstRetainedRoadObjects": duplicate_retained,
        "rejectedNewBuildingConflictRoadObjects": new_building_conflicts,
        "newRoadObjects": len(new_objects),
        "finalRoadObjects": len(objects),
        "frontageConnectors": len(frontage_connectors),
        "skippedWaterCells": skipped_water,
        "newRoadObjectsByScope": dict(scope_counts),
        "roadDeduplicatorMerges": deduplicator.merged,
        "outputObjects": str(output_objects.resolve()),
        "outputPlacements": str(output_placements.resolve()),
        "outputNetwork": str(output_network.resolve()),
        "removedConflicts": removed_conflicts,
        "cityFrontage": final_frontage,
    }
    output_report.write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps({key: value for key, value in report.items() if key != "removedConflicts"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
