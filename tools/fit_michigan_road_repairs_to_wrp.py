#!/usr/bin/env python3
"""Fit only Michigan physical-gap repair panels to an existing WRP terrain."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from embed_michigan_roads_in_wrp import (
    HeightGrid,
    fit_road_to_terrain,
    locate_object_section_without_empty_requirement,
)


def records(path: Path, key: str) -> tuple[dict, list[dict]]:
    payload = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    values = payload.get(key)
    if not isinstance(values, list):
        raise ValueError(f"{path} has no {key} list")
    return payload, values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-wrp", required=True, type=Path)
    parser.add_argument("--objects", required=True, type=Path)
    parser.add_argument("--placements", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--surface-clearance", type=float, default=0.003)
    args = parser.parse_args()

    layout, heights, _ = locate_object_section_without_empty_requirement(
        args.input_wrp.resolve().read_bytes()
    )
    grid = HeightGrid(heights, layout.terrain_cell_size)
    _, objects = records(args.objects, "Objects")
    placement_payload, placements = records(args.placements, "placements")
    if len(objects) != len(placements):
        raise ValueError("Object and placement counts differ")

    output_placements = [dict(value) for value in placements]
    repairs = []
    for index, item in enumerate(objects):
        if not item.get("_physicalGapRepair"):
            continue
        matrix, stats = fit_road_to_terrain(
            item, grid, args.surface_clearance, "cover"
        )
        output_placements[index] = {
            **output_placements[index],
            "index": index,
            "className": item["name"],
            "matrix": matrix,
        }
        repairs.append(
            {
                "index": index,
                "className": item["name"],
                "chainId": item.get("_chainId"),
                **stats,
            }
        )
    if not repairs:
        raise ValueError("No _physicalGapRepair panels were found")

    placement_payload["placements"] = output_placements
    placement_payload["repairTerrainFit"] = {
        "inputWrp": str(args.input_wrp.resolve()),
        "surfaceClearanceMeters": args.surface_clearance,
        "objects": len(repairs),
        "placementMode": "cover",
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(placement_payload, indent=2) + "\n", encoding="ascii"
    )
    report = {
        "schemaVersion": 1,
        "inputWrp": str(args.input_wrp.resolve()),
        "sourcePlacements": str(args.placements.resolve()),
        "outputPlacements": str(args.output.resolve()),
        "repairObjects": len(repairs),
        "surfaceClearanceMeters": args.surface_clearance,
        "minimumClearanceMeters": min(value["minClearance"] for value in repairs),
        "maximumClearanceMeters": max(value["maxClearance"] for value in repairs),
        "maximumTerrainInsetMeters": max(value["terrainInset"] for value in repairs),
        "maximumRightSlopeDegrees": max(
            abs(value["rightSlopeDegrees"]) for value in repairs
        ),
        "maximumForwardSlopeDegrees": max(
            abs(value["forwardSlopeDegrees"]) for value in repairs
        ),
        "repairs": repairs,
    }
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.report.resolve().write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps({key: value for key, value in report.items() if key != "repairs"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
