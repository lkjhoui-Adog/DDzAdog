#!/usr/bin/env python3
"""Lower terrain beneath fixed native Michigan road planes without raising roads."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from embed_michigan_roads_in_wrp import (
    HeightGrid,
    arc_point,
    fit_road_to_terrain,
    road_dimensions,
)
from grade_michigan_road_objects_into_heightmap import (
    family_shoulder_radius,
    nearest_polyline,
    read_asc,
    smoothstep,
    write_asc,
)


def seat_object(
    item: dict,
    matrix: list[float],
    header: dict[str, float],
    shape: tuple[int, int],
    core_target: np.ndarray,
    shoulder_target_sum: np.ndarray,
    shoulder_weight_sum: np.ndarray,
    shoulder_alpha: np.ndarray,
    terrain_gap: float,
    grid_padding: float,
    shoulder_blend_width: float,
    core_mode: str,
) -> int:
    class_name = str(item["name"])
    half_width, module_length, curvature = road_dimensions(class_name)
    # The fixed matrix already carries uniform object scale. Terrain deposition
    # must use the original model-space footprint before applying that matrix.

    center_x = float(matrix[9])
    center_z = float(matrix[11])
    right = np.asarray(matrix[0:3], dtype=np.float64)
    forward = np.asarray(matrix[6:9], dtype=np.float64)
    matrix_scale = float(np.linalg.norm(right))
    if matrix_scale <= 0.0 or not math.isfinite(matrix_scale):
        raise ValueError(f"Invalid road placement scale for {class_name}")
    origin_y = float(matrix[10])
    horizontal = np.asarray(
        [[right[0], forward[0]], [right[2], forward[2]]],
        dtype=np.float64,
    )
    determinant = float(np.linalg.det(horizontal))
    # Short repair modules are intentionally scaled below half length. Their
    # horizontal determinant remains invertible even when it is below the
    # full-size road-panel threshold.
    if abs(determinant) < 1e-4:
        raise ValueError(f"Degenerate road placement matrix for {class_name}")
    horizontal_inverse = np.linalg.inv(horizontal)

    segment_count = max(6, int(math.ceil(module_length / 3.0)))
    distances = np.linspace(-module_length * 0.5, module_length * 0.5, segment_count + 1)
    local_points = np.asarray([arc_point(float(distance), 0.0, curvature) for distance in distances])
    line_x = center_x + right[0] * local_points[:, 0] + forward[0] * local_points[:, 1]
    line_z = center_z + right[2] * local_points[:, 0] + forward[2] * local_points[:, 1]

    cell = float(header["cellsize"])
    xll = float(header.get("xllcorner", 0.0))
    yll = float(header.get("yllcorner", 0.0))
    rows, cols = shape
    world_height = rows * cell
    core_radius = half_width * matrix_scale + grid_padding
    outer_radius = core_radius + shoulder_blend_width
    bound = module_length * matrix_scale * 0.5 + outer_radius + cell

    col_min = max(0, int(math.floor((center_x - bound - xll) / cell)))
    col_max = min(cols - 1, int(math.ceil((center_x + bound - xll) / cell)))
    z_min = center_z - bound
    z_max = center_z + bound
    row_min = max(0, int(math.floor((world_height - (z_max - yll)) / cell)))
    row_max = min(rows - 1, int(math.ceil((world_height - (z_min - yll)) / cell)))
    if col_min > col_max or row_min > row_max:
        return 0

    row_indexes = np.arange(row_min, row_max + 1)
    col_indexes = np.arange(col_min, col_max + 1)
    row_grid, col_grid = np.meshgrid(row_indexes, col_indexes, indexing="ij")
    point_x = xll + col_grid.astype(np.float64) * cell
    point_z = yll + world_height - row_grid.astype(np.float64) * cell
    distance_to_center, _ = nearest_polyline(point_x, point_z, line_x, line_z, distances)
    affected = distance_to_center <= outer_radius
    if not np.any(affected):
        return 0

    delta = np.stack((point_x - center_x, point_z - center_z), axis=0)
    local = np.einsum("ij,jkl->ikl", horizontal_inverse, delta)
    target = origin_y + right[1] * local[0] + forward[1] * local[1] - terrain_gap
    blend_position = (distance_to_center - core_radius) / max(outer_radius - core_radius, 0.001)
    alpha = 1.0 - smoothstep(blend_position)
    alpha[distance_to_center <= core_radius] = 1.0
    alpha[~affected] = 0.0

    target_view = core_target[row_min : row_max + 1, col_min : col_max + 1]
    sum_view = shoulder_target_sum[row_min : row_max + 1, col_min : col_max + 1]
    weight_view = shoulder_weight_sum[row_min : row_max + 1, col_min : col_max + 1]
    alpha_view = shoulder_alpha[row_min : row_max + 1, col_min : col_max + 1]
    core = distance_to_center <= core_radius
    if core_mode == "maximum":
        np.maximum(target_view, np.where(core, target, -np.inf), out=target_view)
    else:
        np.minimum(target_view, np.where(core, target, np.inf), out=target_view)
    sum_view += (target * alpha).astype(np.float32)
    weight_view += alpha.astype(np.float32)
    np.maximum(alpha_view, alpha.astype(np.float32), out=alpha_view)
    return int(np.count_nonzero(affected))


def save_preview(path: Path, original: np.ndarray, seated: np.ndarray, core: np.ndarray) -> None:
    step = max(1, int(math.ceil(max(original.shape) / 1600)))
    correction = original[::step, ::step] - seated[::step, ::step]
    core_small = core[::step, ::step]
    strength = np.clip(correction / 0.35, 0.0, 1.0)
    image_values = np.zeros((*strength.shape, 3), dtype=np.float32)
    image_values[:, :, 0] = strength
    image_values[:, :, 1] = np.sqrt(strength) * 0.55
    image_values[:, :, 2] = core_small.astype(np.float32) * 0.35
    image = Image.fromarray((image_values * 255.0).astype(np.uint8), mode="RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, image.width, 34), fill=(20, 24, 26))
    draw.text((14, 10), "Terrain lowering beneath fixed road planes", fill=(240, 240, 236))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--objects-json", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--placements-output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--preview", required=True, type=Path)
    parser.add_argument("--terrain-gap", type=float, default=0.003)
    parser.add_argument("--fit-clearance", type=float, default=0.001)
    parser.add_argument("--grid-padding", type=float, default=4.0)
    parser.add_argument("--shoulder-blend-width", type=float, default=8.0)
    parser.add_argument("--max-lowering", type=float, default=0.75)
    parser.add_argument("--max-correction", type=float, default=2.0)
    parser.add_argument("--terrain-mode", choices=("lower", "match", "raise"), default="lower")
    parser.add_argument("--placement-mode", choices=("below", "cover"), default="below")
    args = parser.parse_args()
    if not 0.001 <= args.terrain_gap <= 0.05:
        raise ValueError("--terrain-gap must be between 0.001 and 0.05 meters")
    if not 0.0 <= args.grid_padding <= 15.0:
        raise ValueError("--grid-padding must be between 0 and 15 meters")
    if not 2.0 <= args.shoulder_blend_width <= 30.0:
        raise ValueError("--shoulder-blend-width must be between 2 and 30 meters")

    header, original = read_asc(args.input.resolve())
    objects = json.loads(args.objects_json.resolve().read_text(encoding="utf-8")).get("Objects")
    if not isinstance(objects, list) or not objects:
        raise ValueError("Road object layer is empty")
    cell = float(header["cellsize"])
    height_grid = HeightGrid(np.flipud(original).copy(), cell)

    core_target = np.full_like(
        original,
        -np.inf if args.terrain_mode == "raise" else np.inf,
        dtype=np.float32,
    )
    shoulder_target_sum = np.zeros_like(original, dtype=np.float32)
    shoulder_weight_sum = np.zeros_like(original, dtype=np.float32)
    shoulder_alpha = np.zeros_like(original, dtype=np.float32)
    placements = []
    fit_stats = []
    deposited_cells = 0
    for index, item in enumerate(objects):
        matrix, stats = fit_road_to_terrain(
            item,
            height_grid,
            args.fit_clearance,
            args.placement_mode,
        )
        placements.append(
            {
                "index": index,
                "className": item["name"],
                "matrix": matrix,
            }
        )
        fit_stats.append(stats)
        deposited_cells += seat_object(
            item,
            matrix,
            header,
            original.shape,
            core_target,
            shoulder_target_sum,
            shoulder_weight_sum,
            shoulder_alpha,
            args.terrain_gap,
            args.grid_padding,
            args.shoulder_blend_width,
            "maximum" if args.terrain_mode == "raise" else "minimum",
        )

    active = shoulder_weight_sum > 0.0001
    core = np.isfinite(core_target)
    shoulder_average = original.copy()
    shoulder_average[active] = shoulder_target_sum[active] / shoulder_weight_sum[active]
    if args.terrain_mode == "lower":
        shoulder_lowered = np.minimum(original, shoulder_average)
        seated = original + (shoulder_lowered - original) * shoulder_alpha
        seated[core] = np.minimum(seated[core], core_target[core])
        requested_lowering = original - seated
        if float(np.max(requested_lowering)) > args.max_lowering:
            raise ValueError(
                f"Required terrain lowering {float(np.max(requested_lowering)):.3f} m exceeds "
                f"limit {args.max_lowering:.3f} m"
            )
    elif args.terrain_mode == "raise":
        shoulder_raised = np.maximum(original, shoulder_average)
        seated = original + (shoulder_raised - original) * shoulder_alpha
        seated[core] = np.maximum(seated[core], core_target[core])
        correction = seated - original
        if float(np.max(correction)) > args.max_correction:
            raise ValueError(
                f"Required terrain raising {float(np.max(correction)):.3f} m exceeds "
                f"limit {args.max_correction:.3f} m"
            )
        requested_lowering = np.zeros_like(original)
    else:
        seated = original + (shoulder_average - original) * shoulder_alpha
        correction = seated - original
        if float(np.max(np.abs(correction))) > args.max_correction:
            raise ValueError(
                f"Required terrain correction {float(np.max(np.abs(correction))):.3f} m exceeds "
                f"limit {args.max_correction:.3f} m"
            )
        requested_lowering = np.maximum(original - seated, 0.0)
    seated = seated.astype(np.float32)
    write_asc(args.output.resolve(), header, seated)
    save_preview(args.preview.resolve(), original, seated, core)

    args.placements_output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.placements_output.resolve().write_text(
        json.dumps(
            {
                "terrainGapMeters": args.terrain_gap,
                "fitClearanceMeters": args.fit_clearance,
                "terrainMode": args.terrain_mode,
                "placementMode": args.placement_mode,
                "placements": placements,
            },
            indent=2,
        )
        + "\n",
        encoding="ascii",
    )
    lowering = requested_lowering[active]
    raising = np.maximum(seated - original, 0.0)[active]
    absolute_correction = np.abs((seated - original)[active])
    report = {
        "input": str(args.input.resolve()),
        "output": str(args.output.resolve()),
        "objects": len(objects),
        "depositedObjectCells": deposited_cells,
        "activeCells": int(np.count_nonzero(active)),
        "coreCells": int(np.count_nonzero(core)),
        "terrainGapMeters": args.terrain_gap,
        "terrainMode": args.terrain_mode,
        "placementMode": args.placement_mode,
        "meanAbsoluteCorrectionMeters": float(np.mean(absolute_correction)),
        "p95AbsoluteCorrectionMeters": float(np.percentile(absolute_correction, 95.0)),
        "p99AbsoluteCorrectionMeters": float(np.percentile(absolute_correction, 99.0)),
        "maximumAbsoluteCorrectionMeters": float(np.max(absolute_correction)),
        "gridPaddingMeters": args.grid_padding,
        "shoulderBlendWidthMeters": args.shoulder_blend_width,
        "meanLoweringMeters": float(np.mean(lowering)),
        "p95LoweringMeters": float(np.percentile(lowering, 95.0)),
        "p99LoweringMeters": float(np.percentile(lowering, 99.0)),
        "maximumLoweringMeters": float(np.max(lowering)),
        "meanRaisingMeters": float(np.mean(raising)),
        "p95RaisingMeters": float(np.percentile(raising, 95.0)),
        "p99RaisingMeters": float(np.percentile(raising, 99.0)),
        "maximumRaisingMeters": float(np.max(raising)),
        "initialMinimumClearanceMeters": float(min(item["minClearance"] for item in fit_stats)),
        "initialMaximumClearanceMeters": float(max(item["maxClearance"] for item in fit_stats)),
        "minimumHeight": float(np.min(seated)),
        "maximumHeight": float(np.max(seated)),
    }
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.report.resolve().write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
