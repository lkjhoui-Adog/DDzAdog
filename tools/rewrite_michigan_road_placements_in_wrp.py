#!/usr/bin/env python3
"""Replace native Michigan road matrices while preserving the settled scene and terrain."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
from pathlib import Path

import numpy as np

from embed_michigan_roads_in_wrp import (
    HeightGrid,
    evaluate_fixed_placement,
    locate_object_section_without_empty_requirement,
    model_filename,
    parse_embedded_objects,
)


OBJECT_HEADER_BYTES = 56


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    return float(np.percentile(np.asarray(values, dtype=np.float64), fraction * 100.0))


def road_suffix_offset(blob: bytes, object_offset: int, count: int) -> int:
    offset = object_offset
    for index in range(count):
        if offset + OBJECT_HEADER_BYTES > len(blob):
            raise ValueError(f"WRP object list is truncated at road {index}")
        path_length = struct.unpack_from("<I", blob, offset + 52)[0]
        if path_length <= 0 or path_length > 4096:
            raise ValueError(f"Invalid road path length at object {index}: {path_length}")
        offset += OBJECT_HEADER_BYTES + path_length
        if offset > len(blob):
            raise ValueError(f"WRP road path is truncated at object {index}")
    return offset


def raw_object_records(blob: bytes, object_offset: int, count: int) -> list[bytes]:
    records = []
    offset = object_offset
    for index in range(count):
        if offset + OBJECT_HEADER_BYTES > len(blob):
            raise ValueError(f"WRP object list is truncated at object {index}")
        path_length = struct.unpack_from("<I", blob, offset + 52)[0]
        if path_length <= 0 or path_length > 4096:
            raise ValueError(f"Invalid object path length at object {index}: {path_length}")
        end = offset + OBJECT_HEADER_BYTES + path_length
        if end > len(blob):
            raise ValueError(f"WRP object path is truncated at object {index}")
        records.append(blob[offset:end])
        offset = end
    if (
        offset + OBJECT_HEADER_BYTES != len(blob)
        or struct.unpack_from("<I", blob, offset + 52)[0] != 0
    ):
        raise ValueError("WRP object records are not followed by the final dummy record")
    return records


def leading_road_count(existing: list[dict]) -> int:
    prefix = "michiganmitten_roads\\models\\roads\\"
    count = 0
    for record in existing:
        if not str(record["path"]).lower().startswith(prefix):
            break
        count += 1
    if count == 0:
        raise ValueError("WRP does not begin with native Michigan road objects")
    return count


def terrain_layout_signature(layout) -> tuple:
    return (
        layout.texture_width,
        layout.texture_height,
        layout.terrain_width,
        layout.terrain_height,
        layout.texture_cell_size,
        layout.terrain_cell_size,
        layout.material_count,
        layout.object_offset,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-wrp", required=True, type=Path)
    parser.add_argument("--objects-json", required=True, type=Path)
    parser.add_argument("--placements-input", required=True, type=Path)
    parser.add_argument("--output-wrp", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--maximum-inset", type=float, default=0.005)
    parser.add_argument(
        "--replace-all-roads",
        action="store_true",
        help="Replace the complete leading road family and assign fresh native object IDs.",
    )
    parser.add_argument(
        "--preserve-source-road-ids",
        action="store_true",
        help="With --replace-all-roads, inherit each output object's source road ID.",
    )
    parser.add_argument(
        "--preserve-retained-road-ids",
        action="store_true",
        help=(
            "With --replace-all-roads, inherit source IDs only for output objects "
            "that provide _sourceRoadOrdinal; assign fresh IDs to added roads."
        ),
    )
    parser.add_argument(
        "--remove-scene-objects",
        type=Path,
        help="Optional JSON containing sceneObjectIds to omit from the settled scene.",
    )
    args = parser.parse_args()

    if (args.preserve_source_road_ids or args.preserve_retained_road_ids) and not args.replace_all_roads:
        raise ValueError("Road ID preservation requires --replace-all-roads")
    if args.preserve_source_road_ids and args.preserve_retained_road_ids:
        raise ValueError("Choose full or retained-only source road ID preservation, not both")

    input_wrp = args.input_wrp.resolve()
    output_wrp = args.output_wrp.resolve()
    if input_wrp == output_wrp:
        raise ValueError("Input and output WRP paths must differ")

    source = input_wrp.read_bytes()
    layout, heights, materials = locate_object_section_without_empty_requirement(source)
    existing = parse_embedded_objects(source, layout)
    payload = json.loads(args.objects_json.resolve().read_text(encoding="utf-8-sig"))
    objects = payload.get("Objects")
    placement_payload = json.loads(
        args.placements_input.resolve().read_text(encoding="utf-8-sig")
    )
    placements = placement_payload.get("placements")
    if not isinstance(objects, list) or not isinstance(placements, list):
        raise ValueError("Road objects and placements must be JSON lists")
    if len(objects) != len(placements):
        raise ValueError("Road object and placement counts do not agree")

    road_prefix = "michiganmitten_roads\\models\\roads\\"
    if args.replace_all_roads:
        source_road_indices = [
            index
            for index, record in enumerate(existing)
            if str(record["path"]).lower().startswith(road_prefix)
        ]
        if not source_road_indices:
            raise ValueError("WRP does not contain native Michigan road objects")
        source_road_count = len(source_road_indices)
        source_road_index_set = set(source_road_indices)
        source_scene_records = [
            record
            for index, record in enumerate(existing)
            if index not in source_road_index_set
        ]
    else:
        source_road_count = leading_road_count(existing)
        source_road_indices = list(range(source_road_count))
        source_road_index_set = set(source_road_indices)
        source_scene_records = existing[source_road_count:]
    remove_scene_ids: set[int] = set()
    if args.remove_scene_objects is not None:
        removal_payload = json.loads(
            args.remove_scene_objects.resolve().read_text(encoding="utf-8-sig")
        )
        values = removal_payload.get("sceneObjectIds")
        if not isinstance(values, list):
            raise ValueError("Scene removal JSON must contain sceneObjectIds")
        remove_scene_ids = {int(value) for value in values}
        scene_ids = {int(record["id"]) for record in source_scene_records}
        missing = sorted(remove_scene_ids - scene_ids)
        if missing:
            raise ValueError(f"Scene removal IDs are not present in the WRP: {missing[:10]}")
    mapped_source_mode = not args.replace_all_roads and any(
        "_sourceWrpRoadIndex" in item for item in objects
    )
    if not mapped_source_mode and not args.replace_all_roads and len(objects) < source_road_count:
        raise ValueError(
            f"Replacement road layer has fewer objects than the WRP source: "
            f"{len(objects)} < {source_road_count}"
        )
    existing_ids = {int(record["id"]) for record in existing}
    next_added_id = max(existing_ids, default=0) + 1
    mapped_source_indices = [
        int(item["_sourceWrpRoadIndex"])
        for item in objects
        if item.get("_sourceWrpRoadIndex") is not None
    ]
    if mapped_source_mode:
        if len(mapped_source_indices) != len(set(mapped_source_indices)):
            raise ValueError("Replacement road layer maps a source WRP road more than once")
        if any(index < 0 or index >= source_road_count for index in mapped_source_indices):
            raise ValueError("Replacement road layer contains an invalid source WRP road index")

    road_count = len(objects)
    source_ordinals = []
    if args.preserve_source_road_ids:
        source_ordinals = [int(item.get("_sourceRoadOrdinal", -1)) for item in objects]
        if any(ordinal < 0 or ordinal >= source_road_count for ordinal in source_ordinals):
            raise ValueError("A preserved source road ordinal is outside the source road family")
        if len(source_ordinals) != len(set(source_ordinals)):
            raise ValueError("A source road ID would be inherited more than once")
    elif args.preserve_retained_road_ids:
        source_ordinals = [
            int(item["_sourceRoadOrdinal"])
            for item in objects
            if item.get("_sourceRoadOrdinal") is not None
        ]
        if any(ordinal < 0 or ordinal >= source_road_count for ordinal in source_ordinals):
            raise ValueError("A retained source road ordinal is outside the source road family")
        if len(source_ordinals) != len(set(source_ordinals)):
            raise ValueError("A retained source road ID would be inherited more than once")
    road_records = []
    road_object_ids = []
    next_new_id = next_added_id
    for index, (item, placement) in enumerate(zip(objects, placements)):
        class_name = str(item.get("name", ""))
        expected_path = f"MichiganMitten_Roads\\models\\roads\\{model_filename(class_name)}"
        if args.replace_all_roads and args.preserve_source_road_ids:
            source_ordinal = int(item["_sourceRoadOrdinal"])
            source_index = source_road_indices[source_ordinal]
            object_id = int(existing[source_index]["id"])
        elif (
            args.replace_all_roads
            and args.preserve_retained_road_ids
            and item.get("_sourceRoadOrdinal") is not None
        ):
            source_ordinal = int(item["_sourceRoadOrdinal"])
            source_index = source_road_indices[source_ordinal]
            object_id = int(existing[source_index]["id"])
        elif args.replace_all_roads:
            object_id = next_new_id
            next_new_id += 1
        elif mapped_source_mode and item.get("_sourceWrpRoadIndex") is not None:
            source_index = int(item["_sourceWrpRoadIndex"])
            embedded = existing[source_index]
            if str(embedded["path"]).lower() != expected_path.lower():
                raise ValueError(
                    f"Mapped native road path mismatch at object {index}, source {source_index}"
                )
            object_id = int(embedded["id"])
        elif mapped_source_mode:
            object_id = next_new_id
            next_new_id += 1
        elif index < source_road_count:
            embedded = existing[index]
            if str(embedded["path"]).lower() != expected_path.lower():
                raise ValueError(f"Native road order mismatch at object {index}")
            object_id = int(embedded["id"])
        else:
            object_id = next_added_id + index - source_road_count
        if int(placement.get("index", -1)) != index or placement.get("className") != class_name:
            raise ValueError(f"Placement order mismatch at road {index}")
        matrix = [float(value) for value in placement.get("matrix", [])]
        if len(matrix) != 12 or not all(np.isfinite(matrix)):
            raise ValueError(f"Invalid placement matrix at road {index}")
        path_bytes = expected_path.encode("ascii")
        road_records.append(
            struct.pack("<12fI", *matrix, object_id)
            + struct.pack("<I", len(path_bytes))
            + path_bytes
        )
        road_object_ids.append(object_id)

    suffix_offset = (
        None
        if args.replace_all_roads
        else road_suffix_offset(source, layout.object_offset, source_road_count)
    )
    retained_scene = [
        record for record in source_scene_records if int(record["id"]) not in remove_scene_ids
    ]
    raw_records = raw_object_records(source, layout.object_offset, len(existing))
    if args.replace_all_roads:
        retained_scene_raw = [
            raw
            for index, (record, raw) in enumerate(zip(existing, raw_records))
            if index not in source_road_index_set and int(record["id"]) not in remove_scene_ids
        ]
    else:
        retained_scene_raw = [
            raw
            for record, raw in zip(existing[source_road_count:], raw_records[source_road_count:])
            if int(record["id"]) not in remove_scene_ids
        ]
    output_wrp.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_wrp.with_suffix(output_wrp.suffix + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(source[: layout.object_offset])
        for record in road_records:
            handle.write(record)
        if args.replace_all_roads or remove_scene_ids:
            for record in retained_scene_raw:
                handle.write(record)
            handle.write(source[layout.dummy_offset :])
        else:
            assert suffix_offset is not None
            handle.write(source[suffix_offset:])
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(output_wrp)

    output = output_wrp.read_bytes()
    output_layout, output_heights, output_materials = locate_object_section_without_empty_requirement(
        output
    )
    embedded_output = parse_embedded_objects(output, output_layout)
    if (
        terrain_layout_signature(output_layout) != terrain_layout_signature(layout)
        or output_materials != materials
    ):
        raise ValueError("Road rewrite changed WRP layout or surface materials")
    if not np.array_equal(output_heights, heights):
        raise ValueError("Road rewrite changed settled terrain heights")
    if args.replace_all_roads:
        preserved_source_road_count = len(source_ordinals)
    else:
        preserved_source_road_count = (
            len(mapped_source_indices) if mapped_source_mode else source_road_count
        )
    removed_road_count = source_road_count - preserved_source_road_count
    added_road_count = (
        road_count - preserved_source_road_count
        if mapped_source_mode or args.replace_all_roads
        else road_count - source_road_count
    )
    if len(embedded_output) != len(existing) - removed_road_count + added_road_count - len(remove_scene_ids):
        raise ValueError("Road rewrite produced an unexpected native object count")
    if embedded_output[road_count:] != retained_scene:
        raise ValueError("Road rewrite changed landmark or building records")
    if [int(item["id"]) for item in embedded_output[:road_count]] != road_object_ids:
        raise ValueError("Road rewrite produced unexpected native road object IDs")
    if not mapped_source_mode and not args.replace_all_roads and [
        item["id"] for item in embedded_output[:source_road_count]
    ] != [item["id"] for item in existing[:source_road_count]]:
        raise ValueError("Road rewrite changed native road object IDs")
    output_ids = [int(item["id"]) for item in embedded_output]
    if len(output_ids) != len(set(output_ids)):
        raise ValueError("Road rewrite produced duplicate native object IDs")

    grid = HeightGrid(output_heights, output_layout.terrain_cell_size)
    surface_stats = []
    bridge_supports = 0
    for item, placement in zip(objects, placements):
        if item.get("_bridgeSupportFor"):
            bridge_supports += 1
            continue
        surface_stats.append(
            evaluate_fixed_placement(
                item,
                [float(value) for value in placement["matrix"]],
                grid,
            )
        )
    insets = [float(item["terrainInset"]) for item in surface_stats]
    clearances = [float(item["maxClearance"]) for item in surface_stats]
    maximum_inset = max(insets, default=0.0)
    if maximum_inset > args.maximum_inset:
        raise ValueError(
            f"Final road terrain inset {maximum_inset:.6f} m exceeds {args.maximum_inset:.6f} m"
        )

    report = {
        "inputWrp": str(input_wrp),
        "inputSha256": sha256(input_wrp),
        "outputWrp": str(output_wrp),
        "outputSha256": sha256(output_wrp),
        "outputBytes": output_wrp.stat().st_size,
        "nativeObjects": len(embedded_output),
        "sourceRoadObjects": source_road_count,
        "rewrittenRoadObjects": road_count,
        "preservedSourceRoadObjects": preserved_source_road_count,
        "removedRoadObjects": removed_road_count,
        "addedRoadObjects": added_road_count,
        "mappedSourceMode": mapped_source_mode,
        "replaceAllRoads": args.replace_all_roads,
        "preservedSourceRoadIds": args.preserve_source_road_ids,
        "preservedRetainedRoadIds": args.preserve_retained_road_ids,
        "driveableRoadObjects": len(surface_stats),
        "bridgeSupportObjects": bridge_supports,
        "preservedSceneObjects": len(source_scene_records),
        "removedSceneObjects": len(remove_scene_ids),
        "removedSceneObjectIds": sorted(remove_scene_ids),
        "retainedSceneObjects": len(retained_scene),
        "preservedSceneRecordsExact": True,
        "terrainUnchanged": True,
        "terrainInsetMeters": {
            "p95": percentile(insets, 0.95),
            "p99": percentile(insets, 0.99),
            "maximum": maximum_inset,
        },
        "terrainClearanceMeters": {
            "median": percentile(clearances, 0.5),
            "p95": percentile(clearances, 0.95),
            "p99": percentile(clearances, 0.99),
            "maximum": max(clearances, default=0.0),
        },
    }
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.report.resolve().write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
