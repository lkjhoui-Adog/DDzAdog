#!/usr/bin/env python3
"""Combine MichiganMitten terrain, road, gameplay, install, and parity gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REQUIRED_ADDONS = (
    "MichiganMitten.pbo",
    "MichiganMitten_Buildings.pbo",
    "MichiganMitten_Landmarks.pbo",
    "MichiganMitten_Roads.pbo",
)


def load_json(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


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
    parser.add_argument("--terrain-manifest", required=True, type=Path)
    parser.add_argument("--terrain-audit", required=True, type=Path)
    parser.add_argument("--road-parity", required=True, type=Path)
    parser.add_argument("--ce-validation", required=True, type=Path)
    parser.add_argument("--mission-validation", required=True, type=Path)
    parser.add_argument("--install-report", required=True, type=Path)
    parser.add_argument("--client-mod", required=True, type=Path)
    parser.add_argument("--server-mod", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    terrain = load_json(args.terrain_manifest)
    terrain_audit = load_json(args.terrain_audit)
    roads = load_json(args.road_parity)
    ce = load_json(args.ce_validation)
    mission = load_json(args.mission_validation)
    install = load_json(args.install_report)
    errors: list[str] = []
    warnings: list[str] = []

    if terrain.get("verification", {}).get("status") != "valid":
        errors.append("Terrain candidate manifest is not valid")
    if terrain.get("roads", {}).get("nativeObjects", 0) < 150000:
        errors.append("Native physical road count is unexpectedly low")
    if terrain.get("map", {}).get("tiles") != 1024:
        errors.append("Terrain manifest does not contain 1,024 map tiles")
    if terrain.get("map", {}).get("citiesWithCompleteFrontage") != 28:
        errors.append("Terrain manifest does not report all 28 city frontages")

    if terrain_audit.get("SourceWrpHash") != terrain_audit.get("PackedWrpHash"):
        errors.append("Packed WRP does not match the validated source WRP")
    if terrain_audit.get("SourceNavHash") != terrain_audit.get("PackedNavHash"):
        errors.append("Packed navmesh does not match the validated source navmesh")
    if terrain_audit.get("MapTiles") != 1024:
        errors.append("Terrain package audit does not contain 1,024 map tiles")
    if not terrain_audit.get("ScriptsPresent") or not terrain_audit.get("ConfigBin"):
        errors.append("Terrain package is missing scripts or config.bin")

    if roads.get("cityCount") != 28:
        errors.append("Road parity report does not cover 28 cities")
    if roads.get("failingCities"):
        errors.append(f"Road parity has failing cities: {roads.get('failingCities')}")
    if roads.get("mapOnlyWeakFeatures", 0) != 0 or roads.get("selectedWeakFeatures", 0) != 0:
        errors.append("Road parity contains weak or map-only road features")

    if ce.get("status") != "valid" or ce.get("errors"):
        errors.append("Central Economy validation failed")
    if ce.get("mapGroupPlacements", 0) < 4000:
        errors.append("Central Economy contains too few map group placements")
    if ce.get("placementExpandedLootPoints", 0) < 20000:
        errors.append("Central Economy contains too few placement-expanded loot points")
    if ce.get("territories", {}).get("zombie_territories.xml", 0) < 300:
        errors.append("Central Economy contains too few infected territories")

    if mission.get("status") != "valid" or mission.get("errors"):
        errors.append("Installed mission validation failed")
    if mission.get("forbiddenArtifacts"):
        errors.append("Installed mission contains persistence or backup artifacts")
    if mission.get("economyTypes", 0) < 1500:
        errors.append("Installed mission economy type count is unexpectedly low")
    if mission.get("freshPlayerSpawns", 0) < 4:
        errors.append("Installed mission contains too few fresh player spawns")

    if install.get("status") != "installed" or not install.get("hashesVerified"):
        errors.append("Gameplay mission install is not hash-verified")
    if install.get("storagePresentAfterInstall"):
        errors.append("Gameplay mission was not installed with fresh CE storage")
    if install.get("serverStarted") or install.get("dayZStarted"):
        errors.append("Installer unexpectedly started DayZ or the server")

    client = args.client_mod.resolve()
    server = args.server_mod.resolve()
    addon_hashes: dict[str, dict[str, str | bool]] = {}
    for name in REQUIRED_ADDONS:
        client_file = client / "Addons" / name
        server_file = server / "Addons" / name
        if not client_file.is_file() or not server_file.is_file():
            errors.append(f"Missing required client/server addon: {name}")
            continue
        client_hash = sha256(client_file)
        server_hash = sha256(server_file)
        match = client_hash == server_hash
        addon_hashes[name] = {"client": client_hash, "server": server_hash, "match": match}
        if not match:
            errors.append(f"Client/server addon hash mismatch: {name}")

    report = {
        "status": "ready-for-live-test" if not errors else "blocked",
        "terrainCandidate": terrain.get("candidateId"),
        "worldSizeMeters": terrain.get("terrain", {}).get("worldSizeMeters"),
        "nativeRoadObjects": terrain.get("roads", {}).get("nativeObjects"),
        "mapTiles": terrain_audit.get("MapTiles"),
        "citiesWithRoadParity": roads.get("cityCount"),
        "mapOnlyWeakRoads": roads.get("mapOnlyWeakFeatures"),
        "mapGroupPlacements": ce.get("mapGroupPlacements"),
        "placementExpandedLootPoints": ce.get("placementExpandedLootPoints"),
        "infectedTerritories": ce.get("territories", {}).get("zombie_territories.xml"),
        "missionFiles": mission.get("fileCount"),
        "economyTypes": mission.get("economyTypes"),
        "freshPlayerSpawns": mission.get("freshPlayerSpawns"),
        "clientServerAddons": addon_hashes,
        "rollbackArchive": install.get("archive"),
        "liveBootPending": True,
        "errors": errors,
        "warnings": warnings,
    }
    write_json(args.output.resolve(), report)
    print(f"MICHIGAN_RELEASE_STATUS={report['status']}")
    print(f"MICHIGAN_RELEASE_ERRORS={len(errors)}")
    print(f"MICHIGAN_RELEASE_ROADS={report['nativeRoadObjects']}")
    print(f"MICHIGAN_RELEASE_LOOT_POINTS={report['placementExpandedLootPoints']}")
    print(f"MICHIGAN_RELEASE_REPORT={args.output.resolve()}")
    if errors:
        for error in errors:
            print(f"ERROR={error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
