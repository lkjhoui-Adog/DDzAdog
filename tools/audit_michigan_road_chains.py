#!/usr/bin/env python3
"""Audit ordered Michigan road chains for missing modules and open seams."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path


MODEL_PATTERN = re.compile(
    r"^(MI_Road_.+?)(?:_Bridge)?_(25|12|6)(?:_Curve_([LR])(\d{2}))?$"
)
MODULE_LENGTHS = {25: 24.5, 12: 12.25, 6: 6.125}


def model_geometry(item: dict) -> tuple[float, float]:
    match = MODEL_PATTERN.match(str(item["name"]))
    if not match:
        raise ValueError(f"Unknown road model: {item['name']}")
    _, size_text, direction, angle_text = match.groups()
    length = MODULE_LENGTHS[int(size_text)] * float(item.get("scale", 1.0))
    angle = math.radians(int(angle_text or 0))
    if direction == "L":
        angle = -angle
    return length, angle


def model_family(item: dict) -> str:
    match = MODEL_PATTERN.match(str(item["name"]))
    if not match:
        raise ValueError(f"Unknown road model: {item['name']}")
    return match.group(1)


def is_drivable(item: dict) -> bool:
    """Return true only for pavement panels, never bridge structure records."""
    if item.get("_bridgeSupportFor") or item.get("_bridgeSupportKind"):
        return False
    class_name = str(item.get("name", ""))
    if any(
        token in class_name
        for token in ("_Support_", "_Pier_", "_Tower_", "_Cable_", "_Hanger_", "_Anchor_")
    ):
        return False
    return MODEL_PATTERN.match(class_name) is not None


def local_endpoint(length: float, angle: float, end: int) -> tuple[float, float]:
    distance = length * 0.5 * end
    if abs(angle) < 1e-9:
        return 0.0, distance
    curvature = angle / length
    value = curvature * distance
    return (1.0 - math.cos(value)) / curvature, math.sin(value) / curvature


def transform(item: dict, local: tuple[float, float]) -> tuple[float, float]:
    yaw = math.radians(float(item["ypr"][0]))
    x, _, z = item["pos"]
    local_x, local_z = local
    return (
        float(x) + local_x * math.cos(yaw) + local_z * math.sin(yaw),
        float(z) - local_x * math.sin(yaw) + local_z * math.cos(yaw),
    )


def endpoint(item: dict, end: int) -> tuple[tuple[float, float], float]:
    length, angle = model_geometry(item)
    point = transform(item, local_endpoint(length, angle, end))
    heading = (float(item["ypr"][0]) + math.degrees(angle) * 0.5 * end) % 360.0
    return point, heading


def angle_delta(first: float, second: float) -> float:
    return ((second - first + 180.0) % 360.0) - 180.0


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return float(ordered[index])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("objects", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--scope-prefix", default="")
    parser.add_argument("--candidate-radius", type=float, default=8.0)
    args = parser.parse_args()

    payload = json.loads(args.objects.resolve().read_text(encoding="utf-8-sig"))
    objects = payload.get("Objects")
    if not isinstance(objects, list):
        raise ValueError("Road object payload has no Objects list")

    chains: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for object_index, item in enumerate(objects):
        if not is_drivable(item):
            continue
        chain_id = item.get("_chainId")
        if not chain_id or (args.scope_prefix and not str(chain_id).startswith(args.scope_prefix)):
            continue
        chains[str(chain_id)].append((object_index, item))

    seams = []
    internal_breaks = []
    chain_ends = []
    for chain_id, members in chains.items():
        members.sort(key=lambda value: (float(value[1].get("_chainDistance", 0.0)), value[0]))
        first_index, first_item = members[0]
        first_point, first_heading = endpoint(first_item, -1)
        chain_ends.append(
            {
                "chainId": chain_id,
                "objectIndex": first_index,
                "kind": "start",
                "point": first_point,
                "outwardHeading": (first_heading + 180.0) % 360.0,
                "family": model_family(first_item),
            }
        )
        last_index, last_item = members[-1]
        last_point, last_heading = endpoint(last_item, 1)
        chain_ends.append(
            {
                "chainId": chain_id,
                "objectIndex": last_index,
                "kind": "end",
                "point": last_point,
                "outwardHeading": last_heading,
                "family": model_family(last_item),
            }
        )

        for (first_object_index, first), (second_object_index, second) in zip(members, members[1:]):
            first_length = float(first.get("_panelLength", model_geometry(first)[0]))
            second_length = float(second.get("_panelLength", model_geometry(second)[0]))
            expected_distance = (first_length + second_length) * 0.5
            source_distance = float(second.get("_chainDistance", 0.0)) - float(
                first.get("_chainDistance", 0.0)
            )
            source_gap = source_distance - expected_distance
            first_point, first_heading = endpoint(first, 1)
            second_point, second_heading = endpoint(second, -1)
            seam_gap = math.dist(first_point, second_point)
            index_gap = int(second.get("_chainIndex", 0)) - int(first.get("_chainIndex", 0)) - 1
            seam = {
                "chainId": chain_id,
                "firstObject": first_object_index,
                "secondObject": second_object_index,
                "firstChainIndex": int(first.get("_chainIndex", 0)),
                "secondChainIndex": int(second.get("_chainIndex", 0)),
                "sourceGapMeters": source_gap,
                "seamGapMeters": seam_gap,
                "headingDeltaDegrees": angle_delta(first_heading, second_heading),
                "position": [
                    (first_point[0] + second_point[0]) * 0.5,
                    (first_point[1] + second_point[1]) * 0.5,
                ],
            }
            seams.append(seam)
            if index_gap > 0 or source_gap > 0.25 or seam_gap > 0.25:
                seam["missingChainCells"] = max(index_gap, int(round(max(0.0, source_gap) / 6.125)))
                internal_breaks.append(seam)

    endpoint_candidates = []
    bucket_size = args.candidate_radius
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, chain_end in enumerate(chain_ends):
        x, z = chain_end["point"]
        buckets[(int(math.floor(x / bucket_size)), int(math.floor(z / bucket_size)))].append(index)
    seen_pairs = set()
    for first_index, first in enumerate(chain_ends):
        x, z = first["point"]
        cell = int(math.floor(x / bucket_size)), int(math.floor(z / bucket_size))
        for cell_x in range(cell[0] - 1, cell[0] + 2):
            for cell_z in range(cell[1] - 1, cell[1] + 2):
                for second_index in buckets.get((cell_x, cell_z), []):
                    if second_index <= first_index:
                        continue
                    pair = first_index, second_index
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    second = chain_ends[second_index]
                    if first["chainId"] == second["chainId"]:
                        continue
                    dx = second["point"][0] - x
                    dz = second["point"][1] - z
                    distance = math.hypot(dx, dz)
                    if not (0.25 < distance <= args.candidate_radius):
                        continue
                    toward_second = math.degrees(math.atan2(dx, dz)) % 360.0
                    first_alignment = abs(angle_delta(first["outwardHeading"], toward_second))
                    second_alignment = abs(
                        angle_delta(second["outwardHeading"], (toward_second + 180.0) % 360.0)
                    )
                    if first_alignment > 35.0 or second_alignment > 35.0:
                        continue
                    endpoint_candidates.append(
                        {
                            "first": first,
                            "second": second,
                            "distanceMeters": distance,
                            "firstAlignmentDegrees": first_alignment,
                            "secondAlignmentDegrees": second_alignment,
                            "position": [(x + second["point"][0]) * 0.5, (z + second["point"][1]) * 0.5],
                        }
                    )

    seam_gaps = [item["seamGapMeters"] for item in seams]
    report = {
        "objects": len(objects),
        "chains": len(chains),
        "orderedSeams": len(seams),
        "internalBreaks": len(internal_breaks),
        "endpointJoinCandidates": len(endpoint_candidates),
        "seamGapMeters": {
            "median": percentile(seam_gaps, 0.5),
            "p90": percentile(seam_gaps, 0.9),
            "p95": percentile(seam_gaps, 0.95),
            "p99": percentile(seam_gaps, 0.99),
            "maximum": max(seam_gaps, default=0.0),
        },
        "worstSeams": sorted(seams, key=lambda value: value["seamGapMeters"], reverse=True)[:100],
        "breaks": sorted(internal_breaks, key=lambda value: value["seamGapMeters"], reverse=True),
        "endpointCandidates": sorted(endpoint_candidates, key=lambda value: value["distanceMeters"]),
    }
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.report.resolve().write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps({key: value for key, value in report.items() if key not in {"breaks", "endpointCandidates"}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
