#!/usr/bin/env python3
"""Restore genuine dry Michigan road gaps using exact 3D panel placements."""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, mapping, shape
from shapely.strtree import STRtree

from add_michigan_bridges import BASE_MODULE, build_path, crossing_family, endpoint_tangent, path_sample
from build_michigan_road_chain_placements import center_endpoint, make_level_matrix
from build_michigan_statewide_bridge_placements import TerrainSampler
from fill_michigan_road_gaps import gap_module
from embed_michigan_roads_in_wrp import road_dimensions


def read_records(path: Path, key: str) -> tuple[dict, list[dict]]:
    payload = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    records = payload.get(key)
    if not isinstance(records, list) or not records:
        raise ValueError(f"{path} does not contain a non-empty {key} list")
    return payload, records


def validate_layers(objects: list[dict], placements: list[dict]) -> None:
    if len(objects) != len(placements):
        raise ValueError("Object and placement counts do not match")
    for index, (item, placement) in enumerate(zip(objects, placements)):
        if int(placement.get("index", -1)) != index:
            raise ValueError(f"Placement index mismatch at {index}")
        if str(placement.get("className", "")) != str(item.get("name", "")):
            raise ValueError(f"Placement class mismatch at {index}")
        matrix = placement.get("matrix")
        if not isinstance(matrix, list) or len(matrix) != 12:
            raise ValueError(f"Placement matrix is invalid at {index}")
        if not all(math.isfinite(float(value)) for value in matrix):
            raise ValueError(f"Placement matrix is non-finite at {index}")


def clean_prior_repairs(
    objects: list[dict], placements: list[dict]
) -> tuple[list[dict], list[dict], int]:
    clean_objects = []
    clean_placements = []
    removed = 0
    for item, placement in zip(objects, placements):
        if item.get("_physicalGapRepair"):
            removed += 1
            continue
        clean_item = copy.deepcopy(item)
        index = len(clean_objects)
        clean_objects.append(clean_item)
        clean_placements.append(
            {
                "index": index,
                "className": str(clean_item["name"]),
                "matrix": [float(value) for value in placement["matrix"]],
            }
        )
    return clean_objects, clean_placements, removed


def horizontal_tangent(item: dict, matrix: list[float], end: int) -> np.ndarray:
    tangent = endpoint_tangent(item, matrix, end)
    horizontal = np.asarray([float(tangent[0]), float(tangent[2])], dtype=np.float64)
    length = float(np.linalg.norm(horizontal))
    if length <= 1e-8:
        raise ValueError("Road endpoint has no horizontal tangent")
    return horizontal / length


def right_slope(matrix: list[float]) -> float:
    horizontal = math.hypot(float(matrix[0]), float(matrix[2]))
    return float(matrix[1]) / max(horizontal, 1e-8)


def path_nodes(
    points: np.ndarray, cumulative: np.ndarray, panel_count: int
) -> tuple[np.ndarray, np.ndarray]:
    fractions = np.linspace(0.0, 1.0, panel_count + 1)
    nodes = np.asarray(
        [path_sample(points, cumulative, float(fraction)) for fraction in fractions],
        dtype=np.float64,
    )
    distances = np.concatenate(
        (
            np.asarray([0.0]),
            np.cumsum(np.linalg.norm(np.diff(nodes, axis=0), axis=1)),
        )
    )
    return nodes, distances


def append_path(parts: list[np.ndarray], points: np.ndarray) -> None:
    parts.append(points if not parts else points[1:])


def segmented_path(
    waypoints: list[np.ndarray], directions: list[np.ndarray]
) -> tuple[np.ndarray, np.ndarray]:
    parts: list[np.ndarray] = []
    samples_per_leg = max(96, int(math.ceil(512 / max(1, len(waypoints) - 1))))
    for index in range(len(waypoints) - 1):
        points, _ = build_path(
            waypoints[index],
            waypoints[index + 1],
            directions[index],
            directions[index + 1],
            samples=samples_per_leg,
        )
        append_path(parts, points)
    merged = np.concatenate(parts, axis=0)
    cumulative = np.concatenate(
        (np.asarray([0.0]), np.cumsum(np.linalg.norm(np.diff(merged, axis=0), axis=1)))
    )
    return merged, cumulative


def path_hits_obstacles(
    points: np.ndarray,
    obstacle_tree: STRtree | None,
    obstacles: list,
    clearance: float,
) -> list[int]:
    if obstacle_tree is None:
        return []
    corridor = LineString(points).buffer(clearance, quad_segs=8)
    return [
        int(index)
        for index in obstacle_tree.query(corridor, predicate="intersects")
        if corridor.intersection(obstacles[int(index)]).area > 0.01
    ]


def safe_path(
    start: np.ndarray,
    end: np.ndarray,
    start_direction: np.ndarray,
    end_direction: np.ndarray,
    obstacle_tree: STRtree | None,
    obstacles: list,
    road_half_width: float,
    obstacle_clearance: float,
    maximum_bypass_offset: float,
) -> tuple[np.ndarray, np.ndarray, dict]:
    points, cumulative = build_path(start, end, start_direction, end_direction)
    required_clearance = road_half_width + obstacle_clearance
    direct_hits = path_hits_obstacles(points, obstacle_tree, obstacles, required_clearance)
    if not direct_hits:
        return points, cumulative, {"mode": "direct", "obstacles": 0, "offsetMeters": 0.0}

    chord = end - start
    chord_length = float(np.linalg.norm(chord))
    if chord_length <= 0.001:
        raise ValueError("Gap bypass cannot be built for coincident endpoints")
    direction = chord / chord_length
    lateral = np.asarray([direction[1], -direction[0]], dtype=np.float64)
    candidates = []
    minimum_offset = max(road_half_width + obstacle_clearance + 1.0, 5.0)
    offsets = np.arange(minimum_offset, maximum_bypass_offset + 0.001, 2.0)
    for sign in (-1.0, 1.0):
        for offset in offsets:
            waypoint_a = start + chord * 0.34 + lateral * float(offset) * sign
            waypoint_b = start + chord * 0.66 + lateral * float(offset) * sign
            candidate_points, candidate_cumulative = segmented_path(
                [start, waypoint_a, waypoint_b, end],
                [start_direction, direction, direction, end_direction],
            )
            hits = path_hits_obstacles(
                candidate_points,
                obstacle_tree,
                obstacles,
                required_clearance,
            )
            if not hits:
                candidates.append((float(candidate_cumulative[-1]), offset, sign, candidate_points, candidate_cumulative))
                break
    if not candidates:
        raise ValueError(
            f"No building-safe road bypass within {maximum_bypass_offset:.1f}m "
            f"for {len(direct_hits)} obstacle(s)"
        )
    length, offset, sign, points, cumulative = min(candidates, key=lambda value: value[0])
    return points, cumulative, {
        "mode": "building-bypass",
        "obstacles": len(direct_hits),
        "offsetMeters": float(offset) * float(sign),
        "pathLengthMeters": length,
    }


def grade_profile(
    nodes: np.ndarray,
    distances: np.ndarray,
    start_height: float,
    end_height: float,
    sampler: TerrainSampler,
    surface_offset: float,
    maximum_grade_percent: float,
) -> tuple[list[float], dict]:
    total = float(distances[-1])
    ratio = maximum_grade_percent / 100.0
    terrain = [
        float(sampler.sample(float(point[0]), float(point[1]))) for point in nodes
    ]
    lower_bounds = [height + surface_offset for height in terrain]
    lower_bounds[0] = start_height
    lower_bounds[-1] = end_height
    heights = [
        max(
            lower_bound - ratio * abs(float(other_distance - distance))
            for lower_bound, other_distance in zip(lower_bounds, distances)
        )
        for distance in distances
    ]
    start_excess = heights[0] - start_height
    end_excess = heights[-1] - end_height
    if start_excess > 0.003 or end_excess > 0.003:
        raise ValueError(
            "Gap terrain cannot be cleared within the grade limit: "
            f"startExcess={start_excess:.4f}m endExcess={end_excess:.4f}m"
        )
    heights[0] = start_height
    heights[-1] = end_height
    grades = [
        abs(second - first) / max(float(distance_b - distance_a), 0.001) * 100.0
        for first, second, distance_a, distance_b in zip(
            heights, heights[1:], distances, distances[1:]
        )
    ]
    return [float(value) for value in heights], {
        "pathLengthMeters": total,
        "minimumTerrainHeightMeters": min(terrain),
        "maximumTerrainHeightMeters": max(terrain),
        "wetNodeCount": sum(value < 1.0 for value in terrain),
        "maximumGradePercent": max(grades, default=0.0),
        "minimumCenterlineClearanceMeters": min(
            height - terrain_height for height, terrain_height in zip(heights, terrain)
        ),
    }


def feature(line: LineString, properties: dict) -> dict:
    return {"type": "Feature", "properties": properties, "geometry": mapping(line)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objects", type=Path, required=True)
    parser.add_argument("--placements", type=Path, required=True)
    parser.add_argument("--connectivity-report", type=Path, required=True)
    parser.add_argument("--heightmap", type=Path, required=True)
    parser.add_argument("--building-footprints", type=Path)
    parser.add_argument("--special-sites", type=Path)
    parser.add_argument("--output-objects", type=Path, required=True)
    parser.add_argument("--output-placements", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--geojson", type=Path, required=True)
    parser.add_argument("--surface-offset", type=float, default=0.001)
    parser.add_argument("--maximum-grade-percent", type=float, default=8.0)
    parser.add_argument("--obstacle-clearance", type=float, default=2.0)
    parser.add_argument("--maximum-bypass-offset", type=float, default=40.0)
    parser.add_argument(
        "--preserve-prior-repairs",
        action="store_true",
        help="Append a new repair wave without removing existing physical-gap panels.",
    )
    args = parser.parse_args()

    object_payload, source_objects = read_records(args.objects, "Objects")
    placement_payload, source_placements = read_records(args.placements, "placements")
    validate_layers(source_objects, source_placements)
    if args.preserve_prior_repairs:
        objects = copy.deepcopy(source_objects)
        placements = copy.deepcopy(source_placements)
        removed_prior = 0
    else:
        objects, placements, removed_prior = clean_prior_repairs(
            source_objects, source_placements
        )
    validate_layers(objects, placements)

    connectivity = json.loads(
        args.connectivity_report.resolve().read_text(encoding="utf-8-sig")
    )
    land_gaps = [
        item for item in connectivity.get("breaks", []) if item.get("classification") == "land-gap"
    ]
    if not land_gaps:
        raise ValueError("Connectivity report contains no land gaps")

    sampler = TerrainSampler(args.heightmap.resolve())
    obstacle_features = []
    if args.building_footprints:
        obstacle_features.extend(
            json.loads(args.building_footprints.resolve().read_text(encoding="utf-8-sig")).get(
                "features", []
            )
        )
    if args.special_sites:
        obstacle_features.extend(
            feature
            for feature in json.loads(
                args.special_sites.resolve().read_text(encoding="utf-8-sig")
            ).get("features", [])
            if (feature.get("properties") or {}).get("featureType") == "building"
        )
    obstacles = [shape(feature["geometry"]) for feature in obstacle_features]
    obstacle_tree = STRtree(obstacles) if obstacles else None
    repairs = []
    skipped_repairs = []
    repair_features = []
    maximum_internal_horizontal = 0.0
    maximum_internal_vertical = 0.0
    maximum_start_horizontal = 0.0
    maximum_start_vertical = 0.0
    maximum_end_horizontal = 0.0
    maximum_end_vertical = 0.0

    prior_numbers = [
        int(match.group(1))
        for item in objects
        if item.get("_physicalGapRepair")
        for match in [re.match(r"^physical-gap-repair:(\d+):", str(item.get("_chainId", "")))]
        if match
    ]
    first_repair_number = max(prior_numbers, default=0) + 1
    for repair_index, gap in enumerate(land_gaps, start=first_repair_number):
        first_index = int(gap["firstObject"])
        second_index = int(gap["secondObject"])
        first_item = objects[first_index]
        second_item = objects[second_index]
        first_matrix = [float(value) for value in placements[first_index]["matrix"]]
        second_matrix = [float(value) for value in placements[second_index]["matrix"]]
        start_3d = center_endpoint(first_item, first_matrix, 1)
        end_3d = center_endpoint(second_item, second_matrix, -1)
        start = start_3d[[0, 2]]
        end = end_3d[[0, 2]]
        first_direction = horizontal_tangent(first_item, first_matrix, 1)
        second_direction = horizontal_tangent(second_item, second_matrix, -1)
        stem = crossing_family(first_item, second_item)
        road_half_width = road_dimensions(f"{stem}_6")[0]
        dense_points, dense_cumulative, routing = safe_path(
            start,
            end,
            first_direction,
            second_direction,
            obstacle_tree,
            obstacles,
            road_half_width,
            args.obstacle_clearance,
            args.maximum_bypass_offset,
        )
        path_length = float(dense_cumulative[-1])
        requested_panels = max(1, int(gap.get("missingChainCells") or 1))
        panel_count = max(requested_panels, int(math.ceil(path_length / BASE_MODULE)))
        nodes, distances = path_nodes(dense_points, dense_cumulative, panel_count)
        try:
            heights, grade_report = grade_profile(
                nodes,
                distances,
                float(start_3d[1]),
                float(end_3d[1]),
                sampler,
                args.surface_offset,
                args.maximum_grade_percent,
            )
        except ValueError as error:
            skipped_repairs.append(
                {
                    "repairIndex": repair_index,
                    "sourceChain": str(gap["chainId"]),
                    "sourceBreakMeters": float(gap["seamGapMeters"]),
                    "firstSourceObject": first_index,
                    "secondSourceObject": second_index,
                    "reason": str(error),
                    "routing": routing,
                }
            )
            continue
        if grade_report["wetNodeCount"]:
            raise ValueError(f"Land gap unexpectedly touches water: {gap['chainId']}")

        repair_id = f"physical-gap-repair:{repair_index:03d}:{gap['chainId']}"
        start_cross_slope = right_slope(first_matrix)
        end_cross_slope = right_slope(second_matrix)
        grade_degrees = math.degrees(math.atan(args.maximum_grade_percent / 100.0))
        new_items = []
        new_matrices = []
        for panel_index in range(panel_count):
            dummy = {
                "_chainId": repair_id,
                "_roadKey": str(first_item.get("_roadKey") or gap["chainId"]),
                "_chainIndex": panel_index - 1,
                "_chainDistance": float(distances[panel_index]) - BASE_MODULE,
            }
            item = gap_module(
                stem,
                dense_points,
                dense_cumulative,
                panel_index,
                panel_count,
                sampler,
                dummy,
            )
            panel_length = float(distances[panel_index + 1] - distances[panel_index])
            fraction = (
                float(distances[panel_index] + distances[panel_index + 1])
                * 0.5
                / max(float(distances[-1]), 1e-8)
            )
            cross_slope = start_cross_slope * (1.0 - fraction) + end_cross_slope * fraction
            item["_chainId"] = repair_id
            item["_roadKey"] = str(first_item.get("_roadKey") or gap["chainId"])
            item["_chainIndex"] = panel_index
            item["_chainDistance"] = round(
                float(distances[panel_index] + distances[panel_index + 1]) * 0.5, 6
            )
            item["_panelLength"] = round(panel_length, 6)
            item["_physicalGapRepair"] = True
            item["_physicalGapRepairFor"] = str(gap["chainId"])
            item["_condition"] = str(first_item.get("_condition") or "neglected-15-years")
            for source, target in (
                ("_populationScope", "_populationScope"),
                ("_roadClass", "_roadClass"),
                ("_roadName", "_roadName"),
                ("_roadId", "_roadId"),
                ("_routeRef", "_routeRef"),
                ("_speedLimitMph", "_speedLimitMph"),
                ("_cityId", "_cityId"),
                ("_cityName", "_cityName"),
                ("_cityTier", "_cityTier"),
                ("_scope", "_scope"),
            ):
                value = first_item.get(source)
                if value not in {None, ""}:
                    item[target] = value
            matrix = make_level_matrix(
                item,
                heights[panel_index],
                heights[panel_index + 1],
                grade_degrees,
                cross_slope,
            )
            item["pos"][1] = round(float(matrix[10]), 6)
            new_items.append(item)
            new_matrices.append([float(value) for value in matrix])

        start_joint = center_endpoint(new_items[0], new_matrices[0], -1)
        end_joint = center_endpoint(new_items[-1], new_matrices[-1], 1)
        start_horizontal = float(np.linalg.norm(start_joint[[0, 2]] - start_3d[[0, 2]]))
        start_vertical = abs(float(start_joint[1] - start_3d[1]))
        end_horizontal = float(np.linalg.norm(end_joint[[0, 2]] - end_3d[[0, 2]]))
        end_vertical = abs(float(end_joint[1] - end_3d[1]))
        internal_horizontal = []
        internal_vertical = []
        for item_a, matrix_a, item_b, matrix_b in zip(
            new_items, new_matrices, new_items[1:], new_matrices[1:]
        ):
            first_end = center_endpoint(item_a, matrix_a, 1)
            second_start = center_endpoint(item_b, matrix_b, -1)
            internal_horizontal.append(
                float(np.linalg.norm(first_end[[0, 2]] - second_start[[0, 2]]))
            )
            internal_vertical.append(abs(float(first_end[1] - second_start[1])))
        maximum_internal_horizontal = max(
            maximum_internal_horizontal, max(internal_horizontal, default=0.0)
        )
        maximum_internal_vertical = max(
            maximum_internal_vertical, max(internal_vertical, default=0.0)
        )
        maximum_start_horizontal = max(maximum_start_horizontal, start_horizontal)
        maximum_start_vertical = max(maximum_start_vertical, start_vertical)
        maximum_end_horizontal = max(maximum_end_horizontal, end_horizontal)
        maximum_end_vertical = max(maximum_end_vertical, end_vertical)

        first_output_index = len(objects)
        for item, matrix in zip(new_items, new_matrices):
            index = len(objects)
            objects.append(item)
            placements.append(
                {"index": index, "className": str(item["name"]), "matrix": matrix}
            )
        line = LineString([(float(point[0]), float(point[1])) for point in nodes])
        repair_features.append(
            feature(
                line,
                {
                    "id": repair_id,
                    "sourceChain": str(gap["chainId"]),
                    "panels": panel_count,
                    "lengthMeters": round(float(line.length), 3),
                },
            )
        )
        repairs.append(
            {
                "id": repair_id,
                "sourceChain": str(gap["chainId"]),
                "sourceBreakMeters": float(gap["seamGapMeters"]),
                "firstSourceObject": first_index,
                "secondSourceObject": second_index,
                "firstRepairObject": first_output_index,
                "panels": panel_count,
                "routing": routing,
                "startHorizontalSeamMeters": start_horizontal,
                "startVerticalSeamMeters": start_vertical,
                "endHorizontalSeamMeters": end_horizontal,
                "endVerticalSeamMeters": end_vertical,
                **grade_report,
            }
        )

    validate_layers(objects, placements)
    object_payload["Objects"] = objects
    placement_payload["placements"] = placements
    args.output_objects.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output_objects.resolve().write_text(
        json.dumps(object_payload, separators=(",", ":")), encoding="utf-8"
    )
    args.output_placements.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output_placements.resolve().write_text(
        json.dumps(placement_payload, separators=(",", ":")), encoding="utf-8"
    )
    geojson = {
        "type": "FeatureCollection",
        "name": "michigan_physical_land_gap_repairs",
        "schemaVersion": 1,
        "features": repair_features,
    }
    args.geojson.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.geojson.resolve().write_text(json.dumps(geojson, indent=2) + "\n", encoding="ascii")
    report = {
        "schemaVersion": 1,
        "sourceObjects": str(args.objects.resolve()),
        "sourcePlacements": str(args.placements.resolve()),
        "connectivityReport": str(args.connectivity_report.resolve()),
        "heightmap": str(args.heightmap.resolve()),
        "sourceObjectCount": len(source_objects),
        "removedPriorRepairObjects": removed_prior,
        "outputObjectCount": len(objects),
        "repairedLandGaps": len(repairs),
        "skippedLandGaps": len(skipped_repairs),
        "addedRepairObjects": len(objects) - len(source_objects) + removed_prior,
        "maximumInternalHorizontalSeamMeters": maximum_internal_horizontal,
        "maximumInternalVerticalSeamMeters": maximum_internal_vertical,
        "maximumStartHorizontalSeamMeters": maximum_start_horizontal,
        "maximumStartVerticalSeamMeters": maximum_start_vertical,
        "maximumEndHorizontalSeamMeters": maximum_end_horizontal,
        "maximumEndVerticalSeamMeters": maximum_end_vertical,
        "maximumGradePercent": max(
            (float(item["maximumGradePercent"]) for item in repairs), default=0.0
        ),
        "minimumCenterlineClearanceMeters": min(
            (float(item["minimumCenterlineClearanceMeters"]) for item in repairs), default=0.0
        ),
        "repairs": repairs,
        "skippedRepairs": skipped_repairs,
    }
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.report.resolve().write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps({key: value for key, value in report.items() if key != "repairs"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
