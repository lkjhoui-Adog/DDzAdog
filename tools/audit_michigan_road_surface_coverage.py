#!/usr/bin/env python3
"""Verify that classified road gaps are covered by actual pavement footprints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from shapely.geometry import LineString
from shapely.ops import unary_union
from shapely.strtree import STRtree

from build_michigan_road_chain_placements import center_endpoint, matrix_point
from embed_michigan_roads_in_wrp import arc_point, road_dimensions


STRUCTURAL = ("_Support_", "_Pier_", "_Tower_", "_Cable_", "_Hanger_", "_Anchor_")


def values(path: Path, key: str) -> list[dict]:
    result = json.loads(path.resolve().read_text(encoding="utf-8-sig")).get(key)
    if not isinstance(result, list):
        raise ValueError(f"{path} has no {key} list")
    return result


def footprint(item: dict, matrix: list[float]):
    half_width, module_length, curvature = road_dimensions(str(item["name"]))
    sample_count = 9 if abs(curvature) > 1e-9 else 2
    points = []
    for distance in np.linspace(-module_length * 0.5, module_length * 0.5, sample_count):
        local_x, local_z = arc_point(float(distance), 0.0, curvature)
        world = matrix_point(matrix, local_x, local_z)
        points.append((float(world[0]), float(world[2])))
    scale = float(np.linalg.norm(np.asarray(matrix[0:3], dtype=np.float64)))
    return LineString(points).buffer(half_width * scale, cap_style=2, join_style=2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objects", required=True, type=Path)
    parser.add_argument("--placements", required=True, type=Path)
    parser.add_argument("--connectivity", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--classification", default="land-gap")
    args = parser.parse_args()

    objects = values(args.objects, "Objects")
    placements = values(args.placements, "placements")
    if len(objects) != len(placements):
        raise ValueError("Object and placement counts differ")
    connectivity = json.loads(args.connectivity.resolve().read_text(encoding="utf-8-sig"))
    breaks = [
        item
        for item in connectivity.get("breaks", [])
        if item.get("classification") == args.classification
    ]

    polygons = []
    for item, placement in zip(objects, placements):
        if item.get("_bridgeSupportFor") or any(
            token in str(item.get("name", "")) for token in STRUCTURAL
        ):
            continue
        try:
            polygons.append(footprint(item, [float(value) for value in placement["matrix"]]))
        except ValueError:
            continue
    tree = STRtree(polygons)
    results = []
    for item in breaks:
        first = int(item["firstObject"])
        second = int(item["secondObject"])
        start = center_endpoint(objects[first], placements[first]["matrix"], 1)
        end = center_endpoint(objects[second], placements[second]["matrix"], -1)
        segment = LineString([(float(start[0]), float(start[2])), (float(end[0]), float(end[2]))])
        candidates = tree.query(segment.buffer(20.0))
        surface = unary_union([polygons[int(index)] for index in candidates])
        uncovered = float(segment.difference(surface).length)
        results.append(
            {
                "chainId": item["chainId"],
                "firstObject": first,
                "secondObject": second,
                "centerlineGapMeters": float(item["seamGapMeters"]),
                "uncoveredSurfaceMeters": uncovered,
                "coveredByPavementFootprint": uncovered <= 0.001,
                "verticalEndpointDeltaMeters": abs(float(start[1] - end[1])),
            }
        )
    report = {
        "schemaVersion": 1,
        "classification": args.classification,
        "auditedBreaks": len(results),
        "fullySurfaceCovered": sum(value["coveredByPavementFootprint"] for value in results),
        "uncoveredBreaks": sum(not value["coveredByPavementFootprint"] for value in results),
        "maximumUncoveredSurfaceMeters": max(
            (value["uncoveredSurfaceMeters"] for value in results), default=0.0
        ),
        "breaks": results,
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps({key: value for key, value in report.items() if key != "breaks"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
