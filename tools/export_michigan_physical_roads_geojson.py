#!/usr/bin/env python3
"""Export the exact driveable WRP road panels as player-map linework."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from embed_michigan_roads_in_wrp import arc_point, road_dimensions


STRUCTURAL_MARKERS = ("_support_", "_pier_", "_tower_", "_anchor_", "_cable_")


def read_json(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def is_driveable(item: dict, class_name: str) -> bool:
    lower = class_name.lower()
    return not item.get("_bridgeSupportFor") and lower.startswith("mi_road_") and not any(
        marker in lower for marker in STRUCTURAL_MARKERS
    )


def panel_centerline(class_name: str, matrix: list[float]) -> list[list[float]]:
    _, module_length, curvature = road_dimensions(class_name)
    right = np.asarray(matrix[0:3], dtype=np.float64)
    forward = np.asarray(matrix[6:9], dtype=np.float64)
    position = np.asarray(matrix[9:12], dtype=np.float64)
    sample_count = 7 if abs(float(curvature)) > 1.0e-9 else 2
    coordinates = []
    for fraction in np.linspace(-0.5, 0.5, sample_count):
        local_x, local_z = arc_point(module_length * float(fraction), 0.0, curvature)
        world = position + right * local_x + forward * local_z
        coordinates.append([round(float(world[0]), 3), round(float(world[2]), 3)])
    return coordinates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objects", required=True, type=Path)
    parser.add_argument("--placements", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    object_payload = read_json(args.objects)
    placement_payload = read_json(args.placements)
    objects = object_payload.get("Objects")
    placements = placement_payload.get("placements")
    if not isinstance(objects, list) or not isinstance(placements, list):
        raise ValueError("Objects and placements must be JSON lists")
    if len(objects) != len(placements):
        raise ValueError(
            f"Object/placement count mismatch: {len(objects)} != {len(placements)}"
        )

    features = []
    style_counts: dict[str, int] = {}
    city_counts: dict[str, int] = {}
    total_meters = 0.0
    for index, (item, placement) in enumerate(zip(objects, placements)):
        class_name = str(item.get("name") or placement.get("className") or "")
        if not is_driveable(item, class_name):
            continue
        matrix = placement.get("matrix")
        if not isinstance(matrix, list) or len(matrix) != 12:
            raise ValueError(f"Placement {index} has no 12-value matrix")
        _, module_length, _ = road_dimensions(class_name)
        total_meters += float(module_length)

        is_bridge_deck = bool(item.get("_bridgeCrossing"))
        role = "bridge-deck" if is_bridge_deck else "ordinary-road"
        scope = "bridge-deck" if is_bridge_deck else str(item.get("_scope") or "physical")
        city_id = item.get("_cityId")
        properties = {
            "scope": scope,
            "model": class_name,
            "cityId": city_id,
            "roadRole": role,
            "chainId": item.get("_chainId"),
            "roadKey": item.get("_roadKey"),
            "panelIndex": index,
            "physical": True,
        }
        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": {
                    "type": "LineString",
                    "coordinates": panel_centerline(class_name, matrix),
                },
            }
        )
        style_counts[class_name] = style_counts.get(class_name, 0) + 1
        if city_id:
            city_key = str(city_id)
            city_counts[city_key] = city_counts.get(city_key, 0) + 1

    output = {
        "type": "FeatureCollection",
        "name": "MichiganMittenPhysicalRoads",
        "features": features,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, separators=(",", ":")), encoding="ascii")

    report = {
        "objects": str(args.objects.resolve()),
        "placements": str(args.placements.resolve()),
        "output": str(args.output.resolve()),
        "driveablePanels": len(features),
        "sourceMeters": round(total_meters, 3),
        "classCounts": dict(sorted(style_counts.items())),
        "cityCounts": dict(sorted(city_counts.items())),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
