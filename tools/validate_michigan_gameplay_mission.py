#!/usr/bin/env python3
"""Validate a clean MichiganMitten gameplay mission candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from validate_michigan_gameplay_ce import LAND_THRESHOLD, load_height_grid


REQUIRED_FILES = {
    "areaflags.map",
    "cfgeconomycore.xml",
    "cfgeffectarea.json",
    "cfgenvironment.xml",
    "cfgeventgroups.xml",
    "cfgeventspawns.xml",
    "cfggameplay.json",
    "cfgplayerspawnpoints.xml",
    "cfgrandompresets.xml",
    "cfgspawnabletypes.xml",
    "cfgweather.xml",
    "init.c",
    "mapgrouppos.xml",
    "mapgroupproto.xml",
    "db/economy.xml",
    "db/events.xml",
    "db/globals.xml",
    "db/types.xml",
    "env/zombie_territories.xml",
}
FORBIDDEN_PART_PREFIXES = ("storage_", "_backup", "_storage")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mission-dir", required=True, type=Path)
    parser.add_argument("--ce-dir", required=True, type=Path)
    parser.add_argument("--wrp", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    mission = args.mission_dir.resolve()
    ce_dir = args.ce_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    files = sorted(path for path in mission.rglob("*") if path.is_file()) if mission.is_dir() else []
    relative_files = {path.relative_to(mission).as_posix() for path in files}
    for required in sorted(REQUIRED_FILES):
        if required not in relative_files:
            errors.append(f"Missing mission file: {required}")

    forbidden: list[str] = []
    for path in files:
        relative = path.relative_to(mission)
        lowered = [part.lower() for part in relative.parts]
        if any(part.startswith(FORBIDDEN_PART_PREFIXES) for part in lowered):
            forbidden.append(relative.as_posix())
        elif relative.name.lower() in {"players.db", "spawnpoints.bin"}:
            forbidden.append(relative.as_posix())
    if forbidden:
        errors.append(f"Runtime or backup artifacts present: {forbidden[:10]}")

    xml_count = 0
    json_count = 0
    for path in files:
        if path.suffix.lower() == ".xml":
            try:
                ET.parse(path)
                xml_count += 1
            except ET.ParseError as exc:
                errors.append(f"Invalid XML {path.relative_to(mission).as_posix()}: {exc}")
        elif path.suffix.lower() == ".json":
            try:
                json.loads(path.read_text(encoding="utf-8-sig"))
                json_count += 1
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                errors.append(f"Invalid JSON {path.relative_to(mission).as_posix()}: {exc}")

    ce_matches = 0
    for source in sorted(path for path in ce_dir.rglob("*") if path.is_file()):
        relative = source.relative_to(ce_dir)
        target = mission / relative
        if not target.is_file():
            errors.append(f"Missing CE overlay file in mission: {relative.as_posix()}")
        elif sha256(source) != sha256(target):
            errors.append(f"CE overlay hash mismatch: {relative.as_posix()}")
        else:
            ce_matches += 1

    init_path = mission / "init.c"
    init_text = init_path.read_text(encoding="utf-8-sig") if init_path.is_file() else ""
    if "Native terrain roads active" not in init_text:
        errors.append("Mission init does not identify native terrain roads")
    if "LoadMichiganMittenRoads" in init_text or "SpawnMichiganMittenRoadBatch" in init_text:
        errors.append("Mission init contains the superseded runtime road loader")

    type_count = 0
    types_path = mission / "db/types.xml"
    if types_path.is_file():
        try:
            type_count = len(ET.parse(types_path).getroot().findall("type"))
            if type_count < 500:
                errors.append(f"Types economy is unexpectedly small: {type_count}")
        except ET.ParseError:
            pass

    spawn_count = 0
    spawn_groups: set[str] = set()
    height_grid = load_height_grid(args.wrp)
    spawn_path = mission / "cfgplayerspawnpoints.xml"
    if spawn_path.is_file():
        try:
            spawn_root = ET.parse(spawn_path).getroot()
            for group in spawn_root.findall("./fresh/generator_posbubbles/group"):
                spawn_groups.add(str(group.attrib.get("name", "")))
                for position in group.findall("pos"):
                    try:
                        x = float(position.attrib["x"])
                        z = float(position.attrib["z"])
                    except (KeyError, ValueError) as exc:
                        errors.append(f"Invalid player spawn: {exc}")
                        continue
                    if not (math.isfinite(x) and math.isfinite(z)):
                        errors.append("Non-finite player spawn coordinate")
                    elif height_grid.sample(x, z) < LAND_THRESHOLD:
                        errors.append(f"Player spawn is in water: {x:.3f},{z:.3f}")
                    spawn_count += 1
        except ET.ParseError:
            pass
    if spawn_count < 4:
        errors.append(f"Too few fresh player spawns: {spawn_count}")
    if "Hometown" not in spawn_groups:
        errors.append("Fresh player spawns are not grouped at Hometown")

    effect_path = mission / "cfgeffectarea.json"
    if effect_path.is_file():
        try:
            effect_config = json.loads(effect_path.read_text(encoding="utf-8-sig"))
            if effect_config.get("Areas") or effect_config.get("SafePositions"):
                errors.append("Mission contains inherited Chernarus contaminated-area coordinates")
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    environment_path = mission / "cfgenvironment.xml"
    if environment_path.is_file():
        try:
            environment_root = ET.parse(environment_path).getroot()
            environment_paths = [
                str(item.attrib.get("path", ""))
                for item in environment_root.findall("./territories/file")
            ]
            duplicates = sorted({path for path in environment_paths if environment_paths.count(path) > 1})
            if duplicates:
                errors.append(f"Environment contains duplicate territory file references: {duplicates}")
        except ET.ParseError:
            pass

    report = {
        "status": "valid" if not errors else "invalid",
        "missionDirectory": str(mission),
        "wrp": str(args.wrp.resolve()),
        "fileCount": len(files),
        "totalBytes": sum(path.stat().st_size for path in files),
        "xmlFiles": xml_count,
        "jsonFiles": json_count,
        "ceFilesMatched": ce_matches,
        "economyTypes": type_count,
        "freshPlayerSpawns": spawn_count,
        "freshSpawnGroups": sorted(spawn_groups),
        "forbiddenArtifacts": forbidden,
        "errors": errors,
        "warnings": warnings,
    }
    write_json(args.report.resolve(), report)
    print(f"MICHIGAN_MISSION_STATUS={report['status']}")
    print(f"MICHIGAN_MISSION_FILES={len(files)}")
    print(f"MICHIGAN_MISSION_XML={xml_count}")
    print(f"MICHIGAN_MISSION_TYPES={type_count}")
    print(f"MICHIGAN_MISSION_SPAWNS={spawn_count}")
    print(f"MICHIGAN_MISSION_ERRORS={len(errors)}")
    print(f"MICHIGAN_MISSION_REPORT={args.report.resolve()}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
