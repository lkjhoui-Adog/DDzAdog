#!/usr/bin/env python3
"""Audit DayZ user-map city lines against selected vectors and physical road panels."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from shapely.geometry import LineString, MultiLineString, Point, mapping, shape
from shapely.strtree import STRtree


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAP_ROADS = (
    ROOT
    / "build"
    / "candidates"
    / "statewide-road-population-20260712-pass1"
    / "statewide-population-roads-world.geojson"
)
DEFAULT_SELECTED_ROADS = (
    ROOT
    / "build"
    / "candidates"
    / "seamless-city-roads-20260715-pass1"
    / "selected-city-streets-world.geojson"
)
DEFAULT_OBJECTS = (
    ROOT
    / "build"
    / "candidates"
    / "intercity-road-repair-20260715-pass1"
    / "MichiganMittenObjects-intercity-shorelines-rerouted.json"
)
DEFAULT_REPORT = ROOT / "build" / "diagnostics" / "michigan-map-road-parity-report.json"
DEFAULT_UNCOVERED = ROOT / "build" / "diagnostics" / "michigan-map-only-city-roads.geojson"


def load_json(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def geometry_lines(geometry) -> list[LineString]:
    if isinstance(geometry, LineString):
        return [geometry]
    if isinstance(geometry, MultiLineString):
        return list(geometry.geoms)
    return []


def city_vector_records(path: Path, require_city_scope: bool) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = defaultdict(list)
    for feature in load_json(path).get("features", []):
        properties = dict(feature.get("properties") or {})
        city_id = str(properties.get("cityId") or "")
        if not city_id:
            continue
        if require_city_scope and str(properties.get("scope") or "") != "city":
            continue
        for part_index, line in enumerate(geometry_lines(shape(feature["geometry"]))):
            if line.length < 0.01:
                continue
            result[city_id].append(
                {
                    "properties": properties,
                    "geometry": line,
                    "partIndex": part_index,
                }
            )
    return dict(result)


def physical_city_panels(
    path: Path,
    vector_records: dict[str, list[dict]],
    association_distance: float,
) -> tuple[dict[str, list[Point]], dict[str, dict[str, float]]]:
    points: dict[str, list[Point]] = defaultdict(list)
    chains: dict[str, dict[str, float]] = defaultdict(dict)
    vector_lines = []
    vector_city_ids = []
    for city_id, records in vector_records.items():
        for record in records:
            vector_lines.append(record["geometry"])
            vector_city_ids.append(city_id)
    vector_tree = STRtree(vector_lines) if vector_lines else None

    for object_index, item in enumerate(load_json(path).get("Objects", [])):
        if item.get("_bridgeSupportFor"):
            continue
        class_name = str(item.get("name") or "").lower()
        if any(
            marker in class_name
            for marker in ("_support_", "_pier_", "_tower_", "_anchor_", "_cable_")
        ):
            continue
        city_id = str(item.get("_cityId") or "")
        position = item.get("pos") or []
        if len(position) < 3:
            continue
        point = Point(float(position[0]), float(position[2]))
        associated = set()
        if city_id:
            associated.add(city_id)
        elif vector_tree is not None:
            for candidate_index in vector_tree.query(
                point,
                predicate="dwithin",
                distance=association_distance,
            ):
                associated.add(vector_city_ids[int(candidate_index)])
        if not associated:
            continue
        chain_id = str(item.get("_chainId") or f"retained:{object_index}")
        source_length = item.get("_sourceGeometryLengthMeters")
        panel_length = float(item.get("_panelLength") or 0.0)
        for associated_city in associated:
            points[associated_city].append(point)
            if source_length is not None:
                chains[associated_city][chain_id] = max(
                    float(source_length),
                    chains[associated_city].get(chain_id, 0.0),
                )
            else:
                chains[associated_city][chain_id] = (
                    chains[associated_city].get(chain_id, 0.0) + panel_length
                )
    return dict(points), dict(chains)


def line_coverage(line: LineString, tree: STRtree | None, spacing: float, threshold: float) -> float:
    if tree is None:
        return 0.0
    intervals = max(1, int(math.ceil(line.length / spacing)))
    covered = 0
    for index in range(intervals + 1):
        point = line.interpolate(line.length * index / intervals)
        if len(tree.query(point, predicate="dwithin", distance=threshold)):
            covered += 1
    return covered / (intervals + 1)


def audit_layer(
    records: dict[str, list[dict]],
    trees: dict[str, STRtree],
    spacing: float,
    threshold: float,
    uncovered_threshold: float,
) -> tuple[dict[str, dict], list[dict]]:
    reports = {}
    uncovered = []
    for city_id in sorted(records):
        total_meters = 0.0
        covered_meters = 0.0
        completely_covered = 0
        weak_features = 0
        for record in records[city_id]:
            line = record["geometry"]
            coverage = line_coverage(line, trees.get(city_id), spacing, threshold)
            total_meters += line.length
            covered_meters += line.length * coverage
            if coverage >= 0.98:
                completely_covered += 1
            if coverage < uncovered_threshold:
                weak_features += 1
                properties = dict(record["properties"])
                properties.update(
                    {
                        "parityCoverageRatio": round(coverage, 6),
                        "parityLineMeters": round(line.length, 3),
                        "parityPartIndex": record["partIndex"],
                    }
                )
                uncovered.append(
                    {"type": "Feature", "properties": properties, "geometry": mapping(line)}
                )
        reports[city_id] = {
            "features": len(records[city_id]),
            "lineMeters": round(total_meters, 3),
            "coveredMeters": round(covered_meters, 3),
            "coverageRatio": round(covered_meters / total_meters if total_meters else 1.0, 6),
            "fullyCoveredFeatures": completely_covered,
            "weakFeatures": weak_features,
        }
    return reports, uncovered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-roads", type=Path, default=DEFAULT_MAP_ROADS)
    parser.add_argument("--selected-roads", type=Path, default=DEFAULT_SELECTED_ROADS)
    parser.add_argument("--objects", type=Path, default=DEFAULT_OBJECTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--uncovered", type=Path, default=DEFAULT_UNCOVERED)
    parser.add_argument("--sample-spacing", type=float, default=3.0)
    parser.add_argument("--panel-distance", type=float, default=8.0)
    parser.add_argument("--weak-feature-threshold", type=float, default=0.85)
    parser.add_argument("--minimum-city-coverage", type=float, default=0.985)
    parser.add_argument("--allow-failure", action="store_true")
    args = parser.parse_args()

    if args.sample_spacing <= 0.0 or args.panel_distance <= 0.0:
        raise ValueError("Sample spacing and panel distance must be positive")
    map_records = city_vector_records(args.map_roads, require_city_scope=True)
    selected_records = city_vector_records(args.selected_roads, require_city_scope=False)
    panel_points, chain_lengths = physical_city_panels(
        args.objects,
        selected_records,
        args.panel_distance,
    )
    city_ids = sorted(set(map_records) | set(selected_records) | set(panel_points))
    trees = {
        city_id: STRtree(panel_points[city_id])
        for city_id in city_ids
        if panel_points.get(city_id)
    }

    map_reports, map_uncovered = audit_layer(
        map_records,
        trees,
        args.sample_spacing,
        args.panel_distance,
        args.weak_feature_threshold,
    )
    selected_reports, selected_uncovered = audit_layer(
        selected_records,
        trees,
        args.sample_spacing,
        args.panel_distance,
        args.weak_feature_threshold,
    )

    city_reports = []
    failing = []
    for city_id in city_ids:
        map_report = map_reports.get(
            city_id,
            {"features": 0, "lineMeters": 0.0, "coveredMeters": 0.0, "coverageRatio": 1.0,
             "fullyCoveredFeatures": 0, "weakFeatures": 0},
        )
        selected_report = selected_reports.get(
            city_id,
            {"features": 0, "lineMeters": 0.0, "coveredMeters": 0.0, "coverageRatio": 1.0,
             "fullyCoveredFeatures": 0, "weakFeatures": 0},
        )
        physical_meters = sum(chain_lengths.get(city_id, {}).values())
        report = {
            "cityId": city_id,
            "map": map_report,
            "selected": selected_report,
            "physicalPanels": len(panel_points.get(city_id, [])),
            "physicalChains": len(chain_lengths.get(city_id, {})),
            "physicalSourceMeters": round(physical_meters, 3),
        }
        city_reports.append(report)
        if map_report["coverageRatio"] < args.minimum_city_coverage:
            failing.append(city_id)

    uncovered_document = {
        "type": "FeatureCollection",
        "name": "michigan_map_only_city_roads",
        "features": map_uncovered,
    }
    args.uncovered.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.uncovered.resolve().write_text(
        json.dumps(uncovered_document, separators=(",", ":")), encoding="utf-8"
    )

    report = {
        "schemaVersion": 1,
        "mapRoads": str(args.map_roads.resolve()),
        "selectedRoads": str(args.selected_roads.resolve()),
        "objects": str(args.objects.resolve()),
        "sampleSpacingMeters": args.sample_spacing,
        "panelDistanceMeters": args.panel_distance,
        "minimumCityCoverage": args.minimum_city_coverage,
        "cityCount": len(city_ids),
        "failingCities": failing,
        "mapOnlyWeakFeatures": len(map_uncovered),
        "selectedWeakFeatures": len(selected_uncovered),
        "uncoveredGeoJson": str(args.uncovered.resolve()),
        "cities": city_reports,
    }
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.report.resolve().write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps(report, indent=2))
    if failing and not args.allow_failure:
        raise SystemExit(
            "Map-road parity failed for: " + ", ".join(failing)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
