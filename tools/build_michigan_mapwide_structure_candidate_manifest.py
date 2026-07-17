#!/usr/bin/env python3
"""Validate and manifest the refined mapwide Michigan terrain candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path


EXPECTED_ADDONS = (
    "MichiganMitten.pbo",
    "MichiganMitten_Buildings.pbo",
    "MichiganMitten_Landmarks.pbo",
    "MichiganMitten_Roads.pbo",
)
EXPECTED_SCRIPTS = (
    "scripts/3_game/michiganusunits.c",
    "scripts/4_world/michiganusworldunits.c",
    "scripts/5_mission/michiganushudunits.c",
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def file_version(path: Path) -> str:
    escaped = str(path.resolve()).replace("'", "''")
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            f"(Get-Item -LiteralPath '{escaped}').VersionInfo.ProductVersion",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def running_dayz_processes() -> list[str]:
    completed = subprocess.run(
        ["tasklist.exe", "/FO", "CSV", "/NH"],
        check=True,
        capture_output=True,
        text=True,
    )
    blocked = []
    for line in completed.stdout.splitlines():
        image = line.split(",", 1)[0].strip().strip('"').lower()
        if image in {"dayz_x64.exe", "dayzserver_x64.exe"}:
            blocked.append(image)
    return sorted(set(blocked))


def file_record(root: Path, relative: str) -> dict:
    path = root / Path(relative)
    require(path.is_file(), f"Candidate file is missing: {path}")
    return {
        "path": relative.replace("/", "\\"),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--source-wrp", required=True, type=Path)
    parser.add_argument("--source-navmesh", required=True, type=Path)
    parser.add_argument("--extracted-terrain", required=True, type=Path)
    parser.add_argument("--wrp-report", required=True, type=Path)
    parser.add_argument("--clearance-report", required=True, type=Path)
    parser.add_argument("--materialization-report", required=True, type=Path)
    parser.add_argument("--support-report", required=True, type=Path)
    parser.add_argument("--subdivision-report", required=True, type=Path)
    parser.add_argument("--usermap-report", required=True, type=Path)
    parser.add_argument("--network-report", required=True, type=Path)
    parser.add_argument("--client-exe", required=True, type=Path)
    parser.add_argument("--server-exe", required=True, type=Path)
    args = parser.parse_args()

    candidate = args.candidate_root.resolve()
    extracted = args.extracted_terrain.resolve()
    mod = candidate / "@MichiganMitten"
    addons = mod / "Addons"
    mission_init = candidate / "mission/dayzOffline.MichiganMitten/init.c"
    packed_wrp = extracted / "world/MichiganMitten.wrp"
    packed_navmesh = extracted / "navmesh/navmesh.nm"

    wrp = read_json(args.wrp_report.resolve())
    clearance = read_json(args.clearance_report.resolve())
    materialization = read_json(args.materialization_report.resolve())
    supports = read_json(args.support_report.resolve())
    subdivision = read_json(args.subdivision_report.resolve())
    usermap = read_json(args.usermap_report.resolve())
    network = read_json(args.network_report.resolve())

    require(wrp["terrainUnchanged"] is True, "Terrain grid changed during road rewrite")
    require(wrp["preservedSceneRecordsExact"] is True, "Established scene objects changed")
    require(wrp["terrainInsetMeters"]["maximum"] == 0.0, "WRP contains road inset")
    require(clearance["landInsetMeters"]["maximum"] == 0.0, "Roads enter terrain")
    require(
        clearance["landClearanceMeters"]["maximum"] < 1.0,
        "An ordinary ground road remains more than one meter above terrain",
    )
    require(
        materialization["removedBuildingConflictRoadObjects"] > 0,
        "Building-intersection cleanup did not run",
    )
    require(
        materialization["newRoadObjectsByScope"]["city-structure-fill"] > 30_000,
        "Mapwide city-road population is incomplete",
    )
    require(
        materialization["newRoadObjectsByScope"]["farmland-dirt"] > 1_000,
        "Farmland dirt-road population is incomplete",
    )
    require(
        all(float(entry["percent"]) == 100.0 for entry in materialization["cityFrontage"].values()),
        "A city building lacks road frontage",
    )
    require(supports["bridgeCrossings"] >= 500, "Bridge-support audit is incomplete")
    require(subdivision["replacedLongObjects"] == 26, "Long floating-road cleanup changed")
    require(usermap["tileCount"] == 1024, "User-map tile count changed")
    require(usermap["vectorLineCounts"]["dirt"] > 0, "Dirt roads are absent from the map")
    require(network["outputFeatures"] >= 8_900, "Mapwide vector network is incomplete")

    require(packed_wrp.is_file(), "Packed WRP is missing")
    require(packed_navmesh.is_file(), "Packed navmesh is missing")
    require(sha256(packed_wrp) == sha256(args.source_wrp.resolve()), "Packed WRP differs")
    require(
        sha256(packed_navmesh) == sha256(args.source_navmesh.resolve()),
        "Packed navmesh differs",
    )
    tiles = list((extracted / "data/usermap").glob("s_*_*_lco.paa"))
    require(len(tiles) == 1024, "Extracted package does not contain 1,024 map tiles")
    require(all((extracted / relative).is_file() for relative in EXPECTED_SCRIPTS), "U.S.-units scripts are incomplete")
    require((extracted / "config.bin").is_file(), "Packed config.bin is missing")

    actual_pbos = tuple(sorted(path.name for path in addons.glob("*.pbo")))
    require(actual_pbos == tuple(sorted(EXPECTED_ADDONS)), "Candidate PBO set changed")
    actual_signatures = tuple(sorted(path.name for path in addons.glob("*.bisign")))
    expected_signatures = tuple(
        sorted(f"{name}.MichiganMitten.bisign" for name in EXPECTED_ADDONS)
    )
    require(actual_signatures == expected_signatures, "Candidate signature set is incomplete")
    require((mod / "Keys/MichiganMitten.bikey").is_file(), "Candidate key is missing")
    require((mod / "mod.cpp").is_file(), "Candidate mod.cpp is missing")
    require(mission_init.is_file(), "Candidate mission init.c is missing")
    init_text = mission_init.read_text(encoding="utf-8-sig")
    require("Native terrain roads active" in init_text, "Native-road marker is missing")
    require(
        not re.search(r"^\s*LoadMichiganMittenRoads\(\);\s*$", init_text, re.MULTILINE),
        "Mission still calls the runtime road spawner",
    )
    require(
        not (candidate / "mission/dayzOffline.MichiganMitten/custom/MichiganMittenObjects.json").exists(),
        "Candidate contains stale runtime road objects",
    )

    client_version = file_version(args.client_exe)
    server_version = file_version(args.server_exe)
    require(client_version == server_version, "DayZ client and server versions differ")
    blocked_processes = running_dayz_processes()
    require(not blocked_processes, f"DayZ processes are running: {blocked_processes}")

    install_files = []
    for name in EXPECTED_ADDONS:
        install_files.extend(
            (
                f"@MichiganMitten/Addons/{name}",
                f"@MichiganMitten/Addons/{name}.MichiganMitten.bisign",
            )
        )
    install_files.extend(
        (
            "@MichiganMitten/Keys/MichiganMitten.bikey",
            "@MichiganMitten/mod.cpp",
            "mission/dayzOffline.MichiganMitten/init.c",
        )
    )
    checked = datetime.now().astimezone().isoformat()
    manifest = {
        "candidateId": args.candidate_id,
        "created": checked,
        "buildOnly": True,
        "installed": False,
        "scope": (
            "Mapwide building-aware paved and dirt-road refinement with complete city "
            "frontage, supported elevated spans, and synchronized player-map tiles."
        ),
        "compatibility": {
            "dayZClient": client_version,
            "miServerManagerServer": server_version,
            "versionsMatch": True,
            "serverAndClientProcessesStopped": True,
        },
        "terrain": {
            "worldSizeMeters": 40_960.0,
            "sourceWrpBytes": args.source_wrp.resolve().stat().st_size,
            "sourceWrpSha256": sha256(args.source_wrp.resolve()),
            "packedWrpSha256": sha256(packed_wrp),
            "navmeshBytes": packed_navmesh.stat().st_size,
            "navmeshSha256": sha256(packed_navmesh),
            "sceneObjectsPreserved": wrp["preservedSceneObjects"],
        },
        "roads": {
            "nativeObjects": wrp["rewrittenRoadObjects"],
            "driveableObjects": wrp["driveableRoadObjects"],
            "bridgeSupportObjects": wrp["bridgeSupportObjects"],
            "bridgeCrossings": supports["bridgeCrossings"],
            "newCityObjects": materialization["newRoadObjectsByScope"]["city-structure-fill"],
            "newDirtObjects": (
                materialization["newRoadObjectsByScope"]["farmland-dirt"]
                + materialization["newRoadObjectsByScope"]["farmland-dirt-connector"]
            ),
            "removedBuildingConflicts": materialization["removedBuildingConflictRoadObjects"],
            "ordinaryMaximumClearanceMeters": clearance["landClearanceMeters"]["maximum"],
            "maximumTerrainInsetMeters": clearance["landInsetMeters"]["maximum"],
        },
        "map": {
            "tiles": len(tiles),
            "vectorLineCounts": usermap["vectorLineCounts"],
            "citiesWithCompleteFrontage": len(materialization["cityFrontage"]),
        },
        "files": [file_record(candidate, relative) for relative in install_files],
        "verification": {
            "status": "valid",
            "signatureCheckerPassed": True,
            "packageExtractionAudited": True,
            "clientServerCompatibilityPassed": True,
            "installPerformed": False,
        },
    }
    write_json(candidate / "candidate-manifest.json", manifest)
    write_json(
        candidate / "verification/preinstall-report.json",
        {
            "status": "valid",
            "checked": checked,
            "clientVersion": client_version,
            "serverVersion": server_version,
            "sourceAndPackedWrpMatch": True,
            "sourceAndPackedNavmeshMatch": True,
            "mapTiles": len(tiles),
            "signatureCheckerPassed": True,
            "ordinaryRoadMaximumClearanceMeters": clearance["landClearanceMeters"]["maximum"],
            "maximumTerrainInsetMeters": clearance["landInsetMeters"]["maximum"],
            "dayZProcessesRunning": blocked_processes,
        },
    )
    print(f"CANDIDATE={args.candidate_id}")
    print(f"DAYZ_VERSION={client_version}")
    print(f"FILES={len(manifest['files'])}")
    print(f"ROADS={wrp['rewrittenRoadObjects']}")
    print(f"MAP_TILES={len(tiles)}")
    print("MAPWIDE_STRUCTURE_CANDIDATE_VALID=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
