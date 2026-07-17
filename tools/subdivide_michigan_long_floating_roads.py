#!/usr/bin/env python3
"""Replace long floating Michigan road panels with terrain-fitted 6 m panels."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from shapely.geometry import LineString

from embed_michigan_roads_in_wrp import (
    HeightGrid,
    arc_point,
    evaluate_fixed_placement,
    fit_road_to_terrain,
    fixed_placement_clearance_samples,
    locate_object_section_without_empty_requirement,
    road_dimensions,
)
from generate_michigan_mitten_roads import (
    PANEL_LENGTHS,
    RoadDeduplicator,
    append_curve_panel,
    base_family_model,
    measure_panel,
)


def centerline(item: dict, matrix: list[float]) -> LineString:
    _, module_length, curvature = road_dimensions(str(item["name"]))
    right = np.asarray(matrix[0:3], dtype=np.float64)
    forward = np.asarray(matrix[6:9], dtype=np.float64)
    position = np.asarray(matrix[9:12], dtype=np.float64)
    sample_count = max(9, int(math.ceil(module_length / 0.75)) + 1)
    points = []
    for distance in np.linspace(-module_length * 0.5, module_length * 0.5, sample_count):
        local_x, local_z = arc_point(float(distance), 0.0, curvature)
        world = position + right * local_x + forward * local_z
        points.append((float(world[0]), float(world[2])))
    return LineString(points)


def lift_clear(item: dict, matrix: list[float], grid: HeightGrid) -> list[float]:
    adjusted = [float(value) for value in matrix]
    inset = float(evaluate_fixed_placement(item, adjusted, grid)["terrainInset"])
    if inset > 0.0:
        adjusted[10] += inset + 0.001
    return adjusted


def replacement_panels(
    item: dict,
    matrix: list[float],
    grid: HeightGrid,
    object_index: int,
    surface_offset: float,
) -> list[tuple[dict, list[float]]]:
    line = centerline(item, matrix)
    _, module_length, _ = road_dimensions(str(item["name"]))
    cell_count = max(1, int(round(module_length / PANEL_LENGTHS[6])))
    coverage = cell_count * PANEL_LENGTHS[6]
    start_offset = (line.length - coverage) * 0.5
    source_ordinal = item.get("_sourceRoadOrdinal")
    chain_id = f"subdivided-floating:{source_ordinal if source_ordinal is not None else object_index}"
    base_model = base_family_model(str(item["name"]))
    deduplicator = RoadDeduplicator(profile="off")
    inherited = {
        key: value
        for key, value in item.items()
        if key.startswith("_")
        and key
        not in {
            "_bridgeCrossing",
            "_bridgeSupportFor",
            "_junctionViaduct",
            "_sourceRoadOrdinal",
            "_viaduct",
        }
    }

    output = []
    for chain_index in range(cell_count):
        distance = start_offset + (chain_index + 0.5) * PANEL_LENGTHS[6]
        measurement, _ = measure_panel(
            line,
            distance,
            6,
            grid,
            reject_water=False,
        )
        if measurement is None:
            raise ValueError(f"Could not measure replacement panel for object {object_index}")
        measurement.update(
            {
                "source_key": chain_id,
                "road_key": chain_id,
                "chain_index": chain_index,
                "chain_distance": distance,
                "panel_length": PANEL_LENGTHS[6],
            }
        )
        generated: list[dict] = []
        append_curve_panel(generated, deduplicator, base_model, 6, measurement)
        if len(generated) != 1:
            raise ValueError(f"Expected one replacement panel for object {object_index}")
        replacement = generated[0]
        replacement.update(inherited)
        replacement["_chainId"] = chain_id
        replacement["_roadKey"] = chain_id
        replacement["_chainIndex"] = chain_index
        replacement["_chainDistance"] = round(float(distance), 6)
        replacement["_panelLength"] = PANEL_LENGTHS[6]
        replacement["_subdividedLongFloating"] = True
        replacement["_subdividedFromObjectIndex"] = object_index
        if source_ordinal is not None:
            replacement["_subdividedFromSourceRoadOrdinal"] = int(source_ordinal)
            if chain_index == 0:
                replacement["_sourceRoadOrdinal"] = int(source_ordinal)
        fitted, _ = fit_road_to_terrain(
            replacement,
            grid,
            surface_offset,
            placement_mode="cover",
        )
        output.append((replacement, lift_clear(replacement, fitted, grid)))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-wrp", required=True, type=Path)
    parser.add_argument("--objects-json", required=True, type=Path)
    parser.add_argument("--placements-input", required=True, type=Path)
    parser.add_argument("--output-objects", required=True, type=Path)
    parser.add_argument("--output-placements", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--minimum-clearance", type=float, default=1.0)
    parser.add_argument("--surface-offset", type=float, default=0.003)
    args = parser.parse_args()

    layout, height_values, _ = locate_object_section_without_empty_requirement(
        args.input_wrp.resolve().read_bytes()
    )
    grid = HeightGrid(height_values, layout.terrain_cell_size)
    payload = json.loads(args.objects_json.resolve().read_text(encoding="utf-8-sig"))
    placement_payload = json.loads(
        args.placements_input.resolve().read_text(encoding="utf-8-sig")
    )
    objects = payload.get("Objects")
    placements = placement_payload.get("placements")
    if not isinstance(objects, list) or not isinstance(placements, list):
        raise ValueError("Road objects and placements are required")
    if len(objects) != len(placements):
        raise ValueError("Road object and placement counts differ")

    output_objects = []
    output_placements = []
    replaced = []
    replacement_classes = Counter()
    for object_index, (item, record) in enumerate(zip(objects, placements)):
        if int(record.get("index", -1)) != object_index:
            raise ValueError(f"Placement mismatch at object {object_index}")
        matrix = [float(value) for value in record["matrix"]]
        _, module_length, _ = road_dimensions(str(item["name"]))
        samples = fixed_placement_clearance_samples(item, matrix, grid)
        land = [clearance for clearance, terrain in samples if terrain >= 0.0]
        maximum = max(land, default=0.0)
        ordinary = not item.get("_bridgeCrossing") and not item.get("_bridgeSupportFor")
        should_replace = (
            ordinary
            and module_length > 6.2
            and maximum > args.minimum_clearance
        )
        if should_replace:
            replacements = replacement_panels(
                item,
                matrix,
                grid,
                object_index,
                args.surface_offset,
            )
            replacement_maximum = 0.0
            replacement_indices = []
            for replacement, replacement_matrix in replacements:
                new_index = len(output_objects)
                output_objects.append(replacement)
                output_placements.append(
                    {
                        "index": new_index,
                        "className": replacement["name"],
                        "matrix": replacement_matrix,
                    }
                )
                replacement_classes[str(replacement["name"])] += 1
                replacement_indices.append(new_index)
                replacement_land = [
                    clearance
                    for clearance, terrain in fixed_placement_clearance_samples(
                        replacement,
                        replacement_matrix,
                        grid,
                    )
                    if terrain >= 0.0
                ]
                replacement_maximum = max(
                    replacement_maximum,
                    max(replacement_land, default=0.0),
                )
            replaced.append(
                {
                    "inputObjectIndex": object_index,
                    "sourceRoadOrdinal": item.get("_sourceRoadOrdinal"),
                    "className": item["name"],
                    "moduleLengthMeters": module_length,
                    "maximumOriginalClearanceMeters": maximum,
                    "replacementObjectIndices": replacement_indices,
                    "maximumReplacementClearanceMeters": replacement_maximum,
                }
            )
            continue

        new_index = len(output_objects)
        output_objects.append(dict(item))
        output_placements.append(
            {
                **dict(record),
                "index": new_index,
                "className": item["name"],
                "matrix": matrix,
            }
        )

    payload["Objects"] = output_objects
    payload["LongFloatingSubdivision"] = {
        "minimumClearanceMeters": args.minimum_clearance,
        "replacedObjects": len(replaced),
        "replacementObjects": sum(len(item["replacementObjectIndices"]) for item in replaced),
    }
    args.output_objects.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output_objects.resolve().write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="ascii",
    )
    args.output_placements.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output_placements.resolve().write_text(
        json.dumps({"placements": output_placements}, separators=(",", ":")),
        encoding="ascii",
    )
    report = {
        "inputObjects": len(objects),
        "outputObjects": len(output_objects),
        "minimumClearanceMeters": args.minimum_clearance,
        "replacedLongObjects": len(replaced),
        "replacementSixMeterObjects": sum(
            len(item["replacementObjectIndices"]) for item in replaced
        ),
        "replacementClasses": dict(sorted(replacement_classes.items())),
        "maximumOriginalClearanceMeters": max(
            (item["maximumOriginalClearanceMeters"] for item in replaced),
            default=0.0,
        ),
        "maximumReplacementClearanceMeters": max(
            (item["maximumReplacementClearanceMeters"] for item in replaced),
            default=0.0,
        ),
        "replaced": replaced,
    }
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.report.resolve().write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps({key: value for key, value in report.items() if key != "replaced"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
