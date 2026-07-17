#!/usr/bin/env python3
"""Embed generated Michigan road models as native 0WZD terrain objects."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np


MODULE_LENGTHS = {6: 6.125, 12: 12.25, 25: 24.5}
ROAD_HALF_WIDTHS = {
    "MI_Road_Local_2Lane": 3.3,
    "MI_Road_Rural_2Lane": 3.8,
    "MI_Road_Urban_3Lane": 5.6,
    "MI_Road_Urban_4Lane": 7.6,
    "MI_Road_Freeway_4Lane": 9.5,
    "MI_Road_Dirt_Transition_2To4": 7.6,
    "MI_Road_Dirt_Transition_4To2": 7.6,
    "MI_Road_Dirt_4Lane": 7.6,
    "MI_Road_Dirt_2Lane": 3.0,
}
CURVE_RE = re.compile(r"_Curve_([LR])(\d{2})$", flags=re.IGNORECASE)
MODULE_RE = re.compile(r"_(6|12|25)(?:_Curve_|$)", flags=re.IGNORECASE)
JUNCTION_RE = re.compile(r"_Junction_(\d+)$", flags=re.IGNORECASE)
FINAL_OBJECT_BYTES = 56


@dataclass(frozen=True)
class WrpLayout:
    texture_width: int
    texture_height: int
    terrain_width: int
    terrain_height: int
    texture_cell_size: float
    terrain_cell_size: float
    material_count: int
    object_offset: int
    dummy_offset: int


class HeightGrid:
    def __init__(self, values: np.ndarray, cell_size: float):
        self.values = values
        self.height, self.width = values.shape
        self.cell_size = cell_size
        self.world_width = self.width * cell_size
        self.world_height = self.height * cell_size

    def sample(self, x: float, z: float) -> float:
        col = max(0.0, min(self.width - 1.0, x / self.cell_size))
        row = max(0.0, min(self.height - 1.0, z / self.cell_size))
        col0 = int(math.floor(col))
        row0 = int(math.floor(row))
        col1 = min(self.width - 1, col0 + 1)
        row1 = min(self.height - 1, row0 + 1)
        col_mix = col - col0
        row_mix = row - row0
        lower = self.values[row0, col0] * (1.0 - col_mix) + self.values[row0, col1] * col_mix
        upper = self.values[row1, col0] * (1.0 - col_mix) + self.values[row1, col1] * col_mix
        return float(lower * (1.0 - row_mix) + upper * row_mix)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_u32(blob: bytes, offset: int) -> tuple[int, int]:
    if offset + 4 > len(blob):
        raise ValueError(f"Unexpected end of WRP at byte {offset}")
    return struct.unpack_from("<I", blob, offset)[0], offset + 4


def locate_object_section(blob: bytes) -> tuple[WrpLayout, np.ndarray, list[str]]:
    if len(blob) < 24 or blob[:4] != b"0WZD":
        raise ValueError("Input must be an unbinarized DayZ 0WZD WRP")

    texture_width, texture_height, terrain_width, terrain_height = struct.unpack_from("<4i", blob, 4)
    texture_cell_size = struct.unpack_from("<f", blob, 20)[0]
    if min(texture_width, texture_height, terrain_width, terrain_height) <= 0:
        raise ValueError("WRP dimensions must be positive")
    if texture_cell_size <= 0.0 or not math.isfinite(texture_cell_size):
        raise ValueError(f"Invalid WRP texture cell size: {texture_cell_size}")

    terrain_samples = terrain_width * terrain_height
    height_offset = 24
    surface_offset = height_offset + terrain_samples * 4
    material_offset = surface_offset + texture_width * texture_height * 2
    if material_offset + 4 > len(blob):
        raise ValueError("WRP terrain or surface-index grid is incomplete")

    heights = np.frombuffer(blob, dtype="<f4", count=terrain_samples, offset=height_offset)
    if heights.size != terrain_samples or not np.isfinite(heights).all():
        raise ValueError("WRP height grid is incomplete or contains non-finite values")
    heights = heights.reshape(terrain_height, terrain_width)

    material_count, offset = read_u32(blob, material_offset)
    if material_count <= 0 or material_count > 65536:
        raise ValueError(f"Invalid WRP material count: {material_count}")

    materials: list[str] = []
    for material_index in range(material_count):
        segments: list[str] = []
        while True:
            length, offset = read_u32(blob, offset)
            if length == 0:
                break
            if length > 4096 or offset + length > len(blob):
                raise ValueError(f"Invalid material string length {length} at byte {offset - 4}")
            segments.append(blob[offset : offset + length].decode("ascii"))
            offset += length
        name = "".join(segments)
        if material_index == 0:
            if name:
                raise ValueError("WRP material index zero must be empty")
        else:
            materials.append(name)

    object_offset = offset
    object_count = 0
    dummy_offset = -1
    while offset < len(blob):
        if offset + FINAL_OBJECT_BYTES > len(blob):
            raise ValueError(f"Truncated WRP object record at byte {offset}")
        matrix = struct.unpack_from("<12f", blob, offset)
        object_id = struct.unpack_from("<I", blob, offset + 48)[0]
        path_length = struct.unpack_from("<I", blob, offset + 52)[0]
        record_offset = offset
        offset += FINAL_OBJECT_BYTES
        if path_length == 0:
            dummy_offset = record_offset
            if offset != len(blob):
                raise ValueError("WRP dummy object is not the final record")
            if object_count == 0 and not all(math.isnan(value) for value in matrix):
                raise ValueError("Unexpected matrix in empty WRP dummy object")
            if object_count == 0 and object_id == 0:
                raise ValueError("Unexpected zero ID in WRP dummy object")
            break
        if path_length > 4096 or offset + path_length > len(blob):
            raise ValueError(f"Invalid object path length {path_length} at byte {record_offset + 52}")
        offset += path_length
        object_count += 1

    if dummy_offset < 0:
        raise ValueError("WRP does not contain a final dummy object record")
    if object_count:
        raise ValueError(f"Input WRP already contains {object_count} terrain objects")

    terrain_cell_size = texture_cell_size * texture_width / terrain_width
    return (
        WrpLayout(
            texture_width=texture_width,
            texture_height=texture_height,
            terrain_width=terrain_width,
            terrain_height=terrain_height,
            texture_cell_size=texture_cell_size,
            terrain_cell_size=terrain_cell_size,
            material_count=material_count,
            object_offset=object_offset,
            dummy_offset=dummy_offset,
        ),
        heights,
        materials,
    )


def model_filename(class_name: str) -> str:
    prefix = "MI_Road_"
    if not class_name.startswith(prefix):
        raise ValueError(f"Unsupported road class: {class_name}")
    return "mi_" + class_name[len(prefix) :].lower() + ".p3d"


def road_dimensions(class_name: str) -> tuple[float, float, float]:
    half_width = None
    for class_prefix, value in ROAD_HALF_WIDTHS.items():
        if class_name.startswith(class_prefix):
            half_width = value
            break
    if half_width is None:
        raise ValueError(f"Unknown road family: {class_name}")

    junction_match = JUNCTION_RE.search(class_name)
    if junction_match:
        size = float(junction_match.group(1))
        return size * 0.5, size, 0.0

    module_match = MODULE_RE.search(class_name)
    if not module_match:
        raise ValueError(f"Road module length is missing from {class_name}")
    module_length = MODULE_LENGTHS[int(module_match.group(1))]

    curvature = 0.0
    curve_match = CURVE_RE.search(class_name)
    if curve_match:
        sign = -1.0 if curve_match.group(1).upper() == "L" else 1.0
        curvature = sign * math.radians(int(curve_match.group(2))) / module_length
    return half_width, module_length, curvature


def arc_point(distance: float, lateral: float, curvature: float) -> tuple[float, float]:
    if abs(curvature) < 1e-9:
        return lateral, distance
    angle = curvature * distance
    center_x = (1.0 - math.cos(angle)) / curvature
    center_z = math.sin(angle) / curvature
    return center_x + lateral * math.cos(angle), center_z - lateral * math.sin(angle)


def normalize(vector: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    if length <= 1e-9 or not math.isfinite(length):
        raise ValueError(f"Cannot normalize vector {vector.tolist()}")
    return vector / length


def fit_road_to_terrain(
    item: dict,
    heights: HeightGrid,
    surface_offset: float,
    placement_mode: str = "below",
) -> tuple[list[float], dict[str, float]]:
    class_name = str(item["name"])
    position = item["pos"]
    orientation = item["ypr"]
    if len(position) != 3 or len(orientation) != 3:
        raise ValueError(f"Invalid position or orientation for {class_name}")

    center_x = float(position[0])
    center_z = float(position[2])
    yaw = math.radians(float(orientation[0]) % 360.0)
    scale = float(item.get("scale", 1.0))
    if scale <= 0.0 or not math.isfinite(scale):
        raise ValueError(f"Invalid scale {scale} for {class_name}")
    if not (0.0 <= center_x < heights.world_width and 0.0 <= center_z < heights.world_height):
        raise ValueError(f"Road position is outside the WRP: {class_name} at {center_x},{center_z}")

    half_width, module_length, curvature = road_dimensions(class_name)
    half_width *= scale
    module_length *= scale
    curvature /= scale
    right_x, right_z = math.cos(yaw), -math.sin(yaw)
    forward_x, forward_z = math.sin(yaw), math.cos(yaw)

    samples: list[tuple[float, float, float]] = []
    for forward_fraction in (-0.5, -0.25, 0.0, 0.25, 0.5):
        distance = module_length * forward_fraction
        for lateral_fraction in (-1.0, -0.5, 0.0, 0.5, 1.0):
            lateral = half_width * lateral_fraction
            local_x, local_z = arc_point(distance, lateral, curvature)
            world_x = center_x + right_x * local_x + forward_x * local_z
            world_z = center_z + right_z * local_x + forward_z * local_z
            samples.append((local_x, local_z, heights.sample(world_x, world_z)))

    design = np.asarray([[x, z, 1.0] for x, z, _ in samples], dtype=np.float64)
    terrain_values = np.asarray([height for _, _, height in samples], dtype=np.float64)
    fit_design = design
    fit_terrain_values = terrain_values
    if placement_mode == "land-cover":
        land_mask = terrain_values >= 0.0
        if int(np.count_nonzero(land_mask)) >= 3:
            fit_design = design[land_mask]
            fit_terrain_values = terrain_values[land_mask]
    right_slope, forward_slope, intercept = np.linalg.lstsq(
        fit_design,
        fit_terrain_values,
        rcond=None,
    )[0]
    right_slope = float(np.clip(right_slope, -math.tan(math.radians(8.0)), math.tan(math.radians(8.0))))
    forward_slope = float(
        np.clip(forward_slope, -math.tan(math.radians(12.0)), math.tan(math.radians(12.0)))
    )
    intercept = float(
        np.mean(
            fit_terrain_values
            - fit_design[:, 0] * right_slope
            - fit_design[:, 1] * forward_slope
        )
    )

    fitted = design[:, 0] * right_slope + design[:, 1] * forward_slope + intercept
    residual = fitted - terrain_values
    fit_fitted = (
        fit_design[:, 0] * right_slope
        + fit_design[:, 1] * forward_slope
        + intercept
    )
    fit_residual = fit_fitted - fit_terrain_values
    if placement_mode == "below":
        vertical_adjustment = -max(0.0, float(np.max(residual)))
    elif placement_mode == "match":
        vertical_adjustment = 0.0
    elif placement_mode in {"cover", "land-cover"}:
        vertical_adjustment = max(
            0.0,
            -float(np.min(fit_residual if placement_mode == "land-cover" else residual)),
        )
    else:
        raise ValueError(f"Unknown road placement mode: {placement_mode}")
    origin_y = intercept + surface_offset + vertical_adjustment
    placed_plane = fitted + surface_offset + vertical_adjustment
    clearance = placed_plane - terrain_values
    terrain_inset = max(0.0, -float(np.min(clearance)))

    gradient_x = right_slope * right_x + forward_slope * forward_x
    gradient_z = right_slope * right_z + forward_slope * forward_z
    up = normalize(np.asarray([-gradient_x, 1.0, -gradient_z], dtype=np.float64))
    forward_horizontal = np.asarray([forward_x, 0.0, forward_z], dtype=np.float64)
    forward = normalize(forward_horizontal - up * float(np.dot(forward_horizontal, up)))
    right = normalize(np.cross(up, forward))
    forward = normalize(np.cross(right, up))

    matrix = [
        *(right * scale),
        *(up * scale),
        *(forward * scale),
        center_x,
        origin_y,
        center_z,
    ]
    matrix = [float(value) for value in matrix]
    orthogonality = max(
        abs(float(np.dot(right, up))),
        abs(float(np.dot(right, forward))),
        abs(float(np.dot(up, forward))),
    )
    return matrix, {
        "terrainInset": terrain_inset,
        "minClearance": float(np.min(clearance)),
        "maxClearance": float(np.max(clearance)),
        "meanClearance": float(np.mean(clearance)),
        "rightSlopeDegrees": math.degrees(math.atan(right_slope)),
        "forwardSlopeDegrees": math.degrees(math.atan(forward_slope)),
        "orthogonalityError": orthogonality,
        "originY": origin_y,
        "verticalAdjustment": vertical_adjustment,
    }


def fixed_placement_clearance_samples(
    item: dict,
    matrix: list[float],
    heights: HeightGrid,
) -> list[tuple[float, float]]:
    if len(matrix) != 12 or not all(math.isfinite(float(value)) for value in matrix):
        raise ValueError(f"Invalid fixed placement matrix for {item.get('name', '')}")
    class_name = str(item["name"])
    half_width, module_length, curvature = road_dimensions(class_name)
    # Fixed placement matrices already contain the object's uniform scale.
    # Keep the model-space dimensions unscaled here or short repair panels are
    # sampled beyond their real rendered footprint.
    right = np.asarray(matrix[0:3], dtype=np.float64)
    up = np.asarray(matrix[3:6], dtype=np.float64)
    forward = np.asarray(matrix[6:9], dtype=np.float64)
    position = np.asarray(matrix[9:12], dtype=np.float64)
    samples = []
    for forward_fraction in (-0.5, -0.25, 0.0, 0.25, 0.5):
        distance = module_length * forward_fraction
        for lateral_fraction in (-1.0, -0.5, 0.0, 0.5, 1.0):
            lateral = half_width * lateral_fraction
            local_x, local_z = arc_point(distance, lateral, curvature)
            world = position + right * local_x + forward * local_z
            terrain_height = heights.sample(float(world[0]), float(world[2]))
            samples.append((float(world[1] - terrain_height), terrain_height))
    return samples


def evaluate_fixed_placement(
    item: dict,
    matrix: list[float],
    heights: HeightGrid,
) -> dict[str, float]:
    if len(matrix) != 12 or not all(math.isfinite(float(value)) for value in matrix):
        raise ValueError(f"Invalid fixed placement matrix for {item.get('name', '')}")
    right = np.asarray(matrix[0:3], dtype=np.float64)
    up = np.asarray(matrix[3:6], dtype=np.float64)
    forward = np.asarray(matrix[6:9], dtype=np.float64)
    position = np.asarray(matrix[9:12], dtype=np.float64)
    clearance = [
        value for value, _ in fixed_placement_clearance_samples(item, matrix, heights)
    ]
    right_length = max(1e-9, math.hypot(float(right[0]), float(right[2])))
    forward_length = max(1e-9, math.hypot(float(forward[0]), float(forward[2])))
    orthogonality = max(
        abs(float(np.dot(normalize(right), normalize(up)))),
        abs(float(np.dot(normalize(right), normalize(forward)))),
        abs(float(np.dot(normalize(up), normalize(forward)))),
    )
    minimum = min(clearance)
    return {
        "terrainInset": max(0.0, -minimum),
        "minClearance": minimum,
        "maxClearance": max(clearance),
        "meanClearance": float(np.mean(clearance)),
        "rightSlopeDegrees": math.degrees(math.atan(float(right[1]) / right_length)),
        "forwardSlopeDegrees": math.degrees(math.atan(float(forward[1]) / forward_length)),
        "orthogonalityError": orthogonality,
        "originY": float(position[1]),
    }


def parse_embedded_objects(blob: bytes, layout: WrpLayout) -> list[dict]:
    records: list[dict] = []
    offset = layout.object_offset
    while True:
        if offset + FINAL_OBJECT_BYTES > len(blob):
            raise ValueError(f"Truncated embedded object record at byte {offset}")
        matrix = struct.unpack_from("<12f", blob, offset)
        object_id = struct.unpack_from("<I", blob, offset + 48)[0]
        path_length = struct.unpack_from("<I", blob, offset + 52)[0]
        offset += FINAL_OBJECT_BYTES
        if path_length == 0:
            if offset != len(blob):
                raise ValueError("Embedded WRP dummy object is not at EOF")
            break
        if path_length > 4096 or offset + path_length > len(blob):
            raise ValueError(f"Invalid embedded object path length {path_length}")
        path = blob[offset : offset + path_length].decode("ascii")
        offset += path_length
        records.append({"id": object_id, "path": path, "matrix": matrix})
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-wrp", required=True, type=Path)
    parser.add_argument("--objects-json", required=True, type=Path)
    parser.add_argument("--models-root", required=True, type=Path)
    parser.add_argument("--output-wrp", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--id-start", type=int, default=1_000_000)
    parser.add_argument("--surface-offset", type=float, default=0.001)
    parser.add_argument("--max-inset", type=float, default=0.75)
    parser.add_argument("--placements-input", type=Path)
    parser.add_argument("--placement-mode", choices=("below", "cover"), default="below")
    args = parser.parse_args()

    input_wrp = args.input_wrp.resolve()
    objects_json = args.objects_json.resolve()
    models_root = args.models_root.resolve()
    output_wrp = args.output_wrp.resolve()
    report_path = args.report.resolve() if args.report else output_wrp.with_suffix(".report.json")
    if input_wrp == output_wrp:
        raise ValueError("Input and output WRP paths must be different")
    if args.id_start <= 0:
        raise ValueError("--id-start must be positive")
    if args.surface_offset < 0.0 or args.surface_offset > 0.05:
        raise ValueError("--surface-offset must be between 0 and 0.05 meters")

    source_blob = input_wrp.read_bytes()
    # The writer replaces the complete object section, so an existing native
    # road list is a valid source as long as the WRP layout is parseable.
    layout, height_values, materials = locate_object_section_without_empty_requirement(source_blob)
    height_grid = HeightGrid(height_values, layout.terrain_cell_size)
    payload = json.loads(objects_json.read_text(encoding="utf-8"))
    objects = payload.get("Objects")
    if not isinstance(objects, list) or not objects:
        raise ValueError(f"No road objects found in {objects_json}")
    if args.id_start + len(objects) >= 0xFFFFFFFF:
        raise ValueError("Object ID range exceeds uint32")
    fixed_placements = None
    if args.placements_input:
        placement_payload = json.loads(args.placements_input.resolve().read_text(encoding="utf-8"))
        fixed_placements = placement_payload.get("placements")
        if not isinstance(fixed_placements, list) or len(fixed_placements) != len(objects):
            raise ValueError("Fixed placement count does not match road object count")

    records: list[bytes] = []
    expected_paths: list[str] = []
    stats: list[dict[str, float]] = []
    missing_models: list[Path] = []
    for index, item in enumerate(objects):
        class_name = str(item.get("name", ""))
        filename = model_filename(class_name)
        model_file = models_root / filename
        if not model_file.is_file():
            missing_models.append(model_file)
            continue
        path = f"MichiganMitten_Roads\\models\\roads\\{filename}"
        if fixed_placements is None:
            matrix, placement_stats = fit_road_to_terrain(
                item,
                height_grid,
                args.surface_offset,
                args.placement_mode,
            )
        else:
            fixed = fixed_placements[index]
            if int(fixed.get("index", -1)) != index or fixed.get("className") != class_name:
                raise ValueError(f"Fixed placement order mismatch at road {index}")
            matrix = [float(value) for value in fixed.get("matrix", [])]
            placement_stats = evaluate_fixed_placement(item, matrix, height_grid)
        path_bytes = path.encode("ascii")
        object_id = args.id_start + index
        record = struct.pack("<12fI", *matrix, object_id) + struct.pack("<I", len(path_bytes)) + path_bytes
        records.append(record)
        expected_paths.append(path)
        stats.append(placement_stats)

    if missing_models:
        preview = "\n".join(str(path) for path in missing_models[:12])
        raise ValueError(f"Missing {len(missing_models)} road P3D files:\n{preview}")
    if len(records) != len(objects):
        raise ValueError("Road record count changed while embedding")

    surface_stats = [
        placement_stats
        for item, placement_stats in zip(objects, stats)
        if not item.get("_bridgeSupportFor")
    ]
    support_stats = [
        placement_stats
        for item, placement_stats in zip(objects, stats)
        if item.get("_bridgeSupportFor")
    ]
    if not surface_stats:
        raise ValueError("No driveable road or bridge-deck objects found")
    max_inset = max(item["terrainInset"] for item in surface_stats)
    if max_inset > args.max_inset:
        raise ValueError(f"Road terrain inset {max_inset:.3f} m exceeds limit {args.max_inset:.3f} m")

    output_wrp.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_wrp.with_suffix(output_wrp.suffix + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(source_blob[: layout.object_offset])
        for record in records:
            handle.write(record)
        handle.write(source_blob[layout.dummy_offset :])
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(output_wrp)

    output_blob = output_wrp.read_bytes()
    output_layout, output_heights, output_materials = locate_object_section_without_empty_requirement(output_blob)
    embedded = parse_embedded_objects(output_blob, output_layout)
    if len(embedded) != len(objects):
        raise ValueError(f"Embedded object count mismatch: {len(embedded)} != {len(objects)}")
    if [record["path"] for record in embedded] != expected_paths:
        raise ValueError("Embedded model paths do not match the requested road objects")
    ids = [record["id"] for record in embedded]
    if len(ids) != len(set(ids)):
        raise ValueError("Embedded object IDs are not unique")
    if output_materials != materials or not np.array_equal(output_heights, height_values):
        raise ValueError("Embedding changed terrain heights or surface materials")

    report = {
        "inputWrp": str(input_wrp),
        "inputSha256": sha256(input_wrp),
        "outputWrp": str(output_wrp),
        "outputSha256": sha256(output_wrp),
        "outputBytes": output_wrp.stat().st_size,
        "textureGrid": [layout.texture_width, layout.texture_height],
        "terrainGrid": [layout.terrain_width, layout.terrain_height],
        "terrainCellSize": layout.terrain_cell_size,
        "worldSize": layout.terrain_width * layout.terrain_cell_size,
        "surfaceMaterials": len(materials),
        "roadObjects": len(objects),
        "driveableSurfaceObjects": len(surface_stats),
        "bridgeSupportObjects": len(support_stats),
        "uniqueModels": len(set(expected_paths)),
        "objectIdStart": ids[0],
        "objectIdEnd": ids[-1],
        "surfaceOffset": args.surface_offset,
        "placementMode": "fixed" if fixed_placements is not None else args.placement_mode,
        "terrainInset": {
            "mean": float(np.mean([item["terrainInset"] for item in surface_stats])),
            "p95": float(np.percentile([item["terrainInset"] for item in surface_stats], 95)),
            "max": max_inset,
        },
        "clearance": {
            "minimum": min(item["minClearance"] for item in surface_stats),
            "maximum": max(item["maxClearance"] for item in surface_stats),
            "mean": float(np.mean([item["meanClearance"] for item in surface_stats])),
        },
        "slopeDegrees": {
            "maxAbsRight": max(abs(item["rightSlopeDegrees"]) for item in surface_stats),
            "maxAbsForward": max(abs(item["forwardSlopeDegrees"]) for item in surface_stats),
        },
        "maxOrthogonalityError": max(item["orthogonalityError"] for item in surface_stats),
    }
    if support_stats:
        report["bridgeSupportFoundation"] = {
            "terrainInsetMaximum": max(item["terrainInset"] for item in support_stats),
            "clearanceMinimum": min(item["minClearance"] for item in support_stats),
        }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")

    print(f"NATIVE_ROAD_WRP={output_wrp}")
    print(f"NATIVE_ROAD_OBJECTS={len(objects)}")
    print(f"NATIVE_ROAD_MODELS={len(set(expected_paths))}")
    print(f"NATIVE_ROAD_INSET_MEAN={report['terrainInset']['mean']:.6f}")
    print(f"NATIVE_ROAD_INSET_P95={report['terrainInset']['p95']:.6f}")
    print(f"NATIVE_ROAD_INSET_MAX={report['terrainInset']['max']:.6f}")
    print(f"NATIVE_ROAD_CLEARANCE_MAX={report['clearance']['maximum']:.6f}")
    print(f"NATIVE_ROAD_WRP_SHA256={report['outputSha256']}")
    print(f"NATIVE_ROAD_REPORT={report_path}")
    return 0


def locate_object_section_without_empty_requirement(
    blob: bytes,
) -> tuple[WrpLayout, np.ndarray, list[str]]:
    """Parse the common WRP section while permitting an existing object list."""
    if len(blob) < 24 or blob[:4] != b"0WZD":
        raise ValueError("Output must be an unbinarized DayZ 0WZD WRP")
    texture_width, texture_height, terrain_width, terrain_height = struct.unpack_from("<4i", blob, 4)
    texture_cell_size = struct.unpack_from("<f", blob, 20)[0]
    terrain_samples = terrain_width * terrain_height
    heights = np.frombuffer(blob, dtype="<f4", count=terrain_samples, offset=24).reshape(
        terrain_height, terrain_width
    )
    offset = 24 + terrain_samples * 4 + texture_width * texture_height * 2
    material_count, offset = read_u32(blob, offset)
    materials: list[str] = []
    for material_index in range(material_count):
        segments: list[str] = []
        while True:
            length, offset = read_u32(blob, offset)
            if length == 0:
                break
            if length > 4096 or offset + length > len(blob):
                raise ValueError(f"Invalid output material string length {length}")
            segments.append(blob[offset : offset + length].decode("ascii"))
            offset += length
        if material_index:
            materials.append("".join(segments))

    object_offset = offset
    dummy_offset = -1
    while offset < len(blob):
        if offset + FINAL_OBJECT_BYTES > len(blob):
            raise ValueError(f"Truncated existing WRP object record at byte {offset}")
        path_length = struct.unpack_from("<I", blob, offset + 52)[0]
        record_offset = offset
        offset += FINAL_OBJECT_BYTES
        if path_length == 0:
            dummy_offset = record_offset
            if offset != len(blob):
                raise ValueError("Existing WRP dummy object is not the final record")
            break
        if path_length > 4096 or offset + path_length > len(blob):
            raise ValueError(
                f"Invalid existing object path length {path_length} at byte {record_offset + 52}"
            )
        offset += path_length
    if dummy_offset < 0:
        raise ValueError("Existing WRP does not contain a final dummy object record")
    return (
        WrpLayout(
            texture_width=texture_width,
            texture_height=texture_height,
            terrain_width=terrain_width,
            terrain_height=terrain_height,
            texture_cell_size=texture_cell_size,
            terrain_cell_size=texture_cell_size * texture_width / terrain_width,
            material_count=material_count,
            object_offset=object_offset,
            dummy_offset=dummy_offset,
        ),
        heights,
        materials,
    )


if __name__ == "__main__":
    raise SystemExit(main())
