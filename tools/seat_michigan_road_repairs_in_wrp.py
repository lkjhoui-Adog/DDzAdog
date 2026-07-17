#!/usr/bin/env python3
"""Lower terrain locally beneath fixed Michigan road-repair panels in a WRP."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from embed_michigan_roads_in_wrp import (
    arc_point,
    locate_object_section_without_empty_requirement,
    road_dimensions,
)
from seat_michigan_roads_into_heightmap import save_preview


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_records(path: Path, key: str) -> list[dict]:
    payload = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    records = payload.get(key)
    if not isinstance(records, list) or not records:
        raise ValueError(f"{path} does not contain a non-empty {key} list")
    return records


def panel_constraints(
    item: dict,
    matrix: list[float],
    terrain_shape: tuple[int, int],
    cell_size: float,
    terrain_gap: float,
) -> list[tuple[tuple[tuple[int, int], ...], tuple[float, ...], float]]:
    """Return bilinear terrain constraints beneath the rendered panel surface."""
    rows, cols = terrain_shape
    half_width, module_length, curvature = road_dimensions(str(item["name"]))
    right = np.asarray(matrix[0:3], dtype=np.float64)
    forward = np.asarray(matrix[6:9], dtype=np.float64)
    position = np.asarray(matrix[9:12], dtype=np.float64)
    constraints = []
    for forward_fraction in np.linspace(-0.5, 0.5, 9):
        distance = module_length * float(forward_fraction)
        for lateral_fraction in np.linspace(-1.0, 1.0, 7):
            lateral = half_width * float(lateral_fraction)
            local_x, local_z = arc_point(distance, lateral, curvature)
            world = position + right * local_x + forward * local_z
            col = max(0.0, min(cols - 1.0, float(world[0]) / cell_size))
            row = max(0.0, min(rows - 1.0, float(world[2]) / cell_size))
            col0 = int(math.floor(col))
            row0 = int(math.floor(row))
            col1 = min(cols - 1, col0 + 1)
            row1 = min(rows - 1, row0 + 1)
            col_mix = col - col0
            row_mix = row - row0
            indexes = ((row0, col0), (row0, col1), (row1, col0), (row1, col1))
            weights = (
                (1.0 - row_mix) * (1.0 - col_mix),
                (1.0 - row_mix) * col_mix,
                row_mix * (1.0 - col_mix),
                row_mix * col_mix,
            )
            constraints.append((indexes, weights, float(world[1]) - terrain_gap))
    return constraints


def satisfy_constraints(
    original: np.ndarray,
    constraints: list[tuple[tuple[tuple[int, int], ...], tuple[float, ...], float]],
    maximum_lowering: float,
) -> tuple[np.ndarray, float, int]:
    """Project terrain downward until every sampled road point is exposed."""
    seated = original.copy()
    tolerance = 1e-5
    passes = 0
    maximum_violation = 0.0
    for passes in range(1, 65):
        maximum_violation = 0.0
        changed = False
        for indexes, weights, target in constraints:
            current = sum(
                weight * float(seated[row, col])
                for (row, col), weight in zip(indexes, weights)
            )
            excess = current - target
            if excess <= tolerance:
                continue
            maximum_violation = max(maximum_violation, excess)
            adjustable = [
                slot
                for slot, ((row, col), weight) in enumerate(zip(indexes, weights))
                if weight > 1e-9
                and float(original[row, col]) > 0.5
                and float(seated[row, col])
                > float(original[row, col]) - maximum_lowering + tolerance
            ]
            remaining = excess
            while adjustable and remaining > tolerance:
                denominator = sum(weights[slot] ** 2 for slot in adjustable)
                if denominator <= 1e-12:
                    break
                proposed = {
                    slot: remaining * weights[slot] / denominator for slot in adjustable
                }
                saturated = []
                achieved = 0.0
                for slot in adjustable:
                    row, col = indexes[slot]
                    capacity = float(seated[row, col]) - (
                        float(original[row, col]) - maximum_lowering
                    )
                    lowering = min(proposed[slot], capacity)
                    if lowering > 0.0:
                        seated[row, col] -= lowering
                        achieved += weights[slot] * lowering
                        changed = True
                    if capacity <= proposed[slot] + tolerance:
                        saturated.append(slot)
                remaining -= achieved
                adjustable = [slot for slot in adjustable if slot not in saturated]
            if remaining > 0.001:
                raise ValueError(
                    f"Terrain constraint still exceeds road by {remaining:.3f}m after "
                    f"the {maximum_lowering:.3f}m lowering limit"
                )
        if not changed or maximum_violation <= tolerance:
            break
    return seated, maximum_violation, passes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-wrp", type=Path, required=True)
    parser.add_argument("--objects", type=Path, required=True)
    parser.add_argument("--placements", type=Path, required=True)
    parser.add_argument("--output-wrp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--preview", type=Path, required=True)
    parser.add_argument("--terrain-gap", type=float, default=0.003)
    parser.add_argument("--grid-padding", type=float, default=1.0)
    parser.add_argument("--shoulder-blend-width", type=float, default=6.0)
    parser.add_argument("--maximum-lowering", type=float, default=1.5)
    args = parser.parse_args()

    input_wrp = args.input_wrp.resolve()
    output_wrp = args.output_wrp.resolve()
    if input_wrp == output_wrp:
        raise ValueError("Input and output WRP paths must differ")
    source = bytearray(input_wrp.read_bytes())
    layout, height_values, _ = locate_object_section_without_empty_requirement(source)
    objects = read_records(args.objects, "Objects")
    placements = read_records(args.placements, "placements")
    if len(objects) != len(placements):
        raise ValueError("Object and placement counts do not match")

    selected = []
    for index, (item, placement) in enumerate(zip(objects, placements)):
        if not item.get("_physicalGapRepair"):
            continue
        matrix = placement.get("matrix")
        if not isinstance(matrix, list) or len(matrix) != 12:
            raise ValueError(f"Repair placement {index} has an invalid matrix")
        selected.append((index, item, [float(value) for value in matrix]))
    if not selected:
        raise ValueError("No _physicalGapRepair objects were found")

    original = np.asarray(height_values, dtype=np.float32).copy()
    constraints = []
    for _, item, matrix in selected:
        constraints.extend(
            panel_constraints(
                item,
                matrix,
                original.shape,
                float(layout.terrain_cell_size),
                args.terrain_gap,
            )
        )
    seated, remaining_violation, solver_passes = satisfy_constraints(
        original, constraints, args.maximum_lowering
    )
    lowering = original - seated
    maximum = float(np.max(lowering))
    if maximum > args.maximum_lowering + 1e-6:
        raise ValueError(
            f"Required repair lowering {maximum:.3f}m exceeds "
            f"limit {args.maximum_lowering:.3f}m"
        )

    wrp_heights = seated.astype("<f4", copy=False)
    height_offset = 24
    height_bytes = wrp_heights.tobytes(order="C")
    source[height_offset : height_offset + len(height_bytes)] = height_bytes
    output_wrp.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_wrp.with_suffix(output_wrp.suffix + ".tmp")
    temporary.write_bytes(source)
    temporary.replace(output_wrp)
    changed = lowering > 1e-6
    save_preview(
        args.preview.resolve(), np.flipud(original), np.flipud(seated), np.flipud(changed)
    )

    active_lowering = lowering[changed]
    report = {
        "schemaVersion": 1,
        "inputWrp": str(input_wrp),
        "inputSha256": sha256(input_wrp),
        "outputWrp": str(output_wrp),
        "outputSha256": sha256(output_wrp),
        "terrainGrid": [layout.terrain_width, layout.terrain_height],
        "terrainCellSizeMeters": layout.terrain_cell_size,
        "repairObjects": len(selected),
        "surfaceConstraints": len(constraints),
        "solverPasses": solver_passes,
        "remainingViolationMeters": remaining_violation,
        "changedTerrainCells": int(np.count_nonzero(changed)),
        "changedSquareKilometers": float(
            np.count_nonzero(changed) * layout.terrain_cell_size**2 / 1_000_000.0
        ),
        "maximumLoweringMeters": maximum,
        "p95LoweringMeters": float(np.percentile(active_lowering, 95.0)),
        "meanLoweringMeters": float(np.mean(active_lowering)),
        "minimumHeightBefore": float(np.min(original)),
        "minimumHeightAfter": float(np.min(seated)),
        "waterTerrainCellsChanged": 0,
        "terrainGapMeters": args.terrain_gap,
        "shoulderBlendWidthMeters": args.shoulder_blend_width,
    }
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.report.resolve().write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
