#!/usr/bin/env python3
"""Install a validated MichiganMitten mission with an exact rollback archive."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


DAYZ_PROCESSES = {"dayz_x64.exe", "dayzserver_x64.exe", "dayzdiag_x64.exe"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def running_dayz_processes() -> list[str]:
    result = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    found: set[str] = set()
    for line in result.stdout.splitlines():
        first = line.strip().split(",", 1)[0].strip('"').lower()
        if first in DAYZ_PROCESSES:
            found.add(first)
    return sorted(found)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--live-mission", required=True, type=Path)
    parser.add_argument("--archive-root", required=True, type=Path)
    parser.add_argument("--validation-report", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    candidate = args.candidate.resolve()
    live = args.live_mission.resolve()
    archive_root = args.archive_root.resolve()
    validation_report = json.loads(args.validation_report.resolve().read_text(encoding="utf-8"))
    if validation_report.get("status") != "valid":
        raise SystemExit("Mission validation report is not valid")
    if not candidate.is_dir() or not live.is_dir():
        raise SystemExit("Candidate and live mission directories must both exist")
    if candidate.name != "dayzOffline.MichiganMitten" or live.name != "dayzOffline.MichiganMitten":
        raise SystemExit("Refusing to install an unexpected mission directory name")
    if candidate == live or candidate in live.parents or live in candidate.parents:
        raise SystemExit("Candidate and live mission paths overlap")
    running = running_dayz_processes()
    if running:
        raise SystemExit(f"DayZ processes are running: {', '.join(running)}")

    candidate_hashes = file_hashes(candidate)
    if not candidate_hashes:
        raise SystemExit("Candidate mission is empty")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = archive_root / f"pre-gameplay-ce-install-{timestamp}"
    previous = archive / "dayzOffline.MichiganMitten.previous"
    staging = live.parent / f"{live.name}.installing-{timestamp}"
    if archive.exists() or staging.exists():
        raise SystemExit("Archive or staging path already exists")
    archive.mkdir(parents=True)

    try:
        shutil.copytree(candidate, staging)
        staging_hashes = file_hashes(staging)
        if staging_hashes != candidate_hashes:
            raise RuntimeError("Staged mission hashes do not match candidate")
        shutil.move(str(live), str(previous))
        staging.rename(live)
        live_hashes = file_hashes(live)
        if live_hashes != candidate_hashes:
            raise RuntimeError("Installed mission hashes do not match candidate")
    except Exception:
        if live.exists() and previous.exists():
            shutil.rmtree(live)
        if previous.exists() and not live.exists():
            shutil.move(str(previous), str(live))
        if staging.exists():
            shutil.rmtree(staging)
        raise

    report = {
        "status": "installed",
        "installedAt": datetime.now().astimezone().isoformat(),
        "candidate": str(candidate),
        "liveMission": str(live),
        "archive": str(archive),
        "previousMission": str(previous),
        "freshStorageRequired": True,
        "storagePresentAfterInstall": (live / "storage_1").exists(),
        "fileCount": len(candidate_hashes),
        "totalBytes": sum(path.stat().st_size for path in live.rglob("*") if path.is_file()),
        "hashesVerified": True,
        "dayZProcessesRunning": running,
        "serverStarted": False,
        "dayZStarted": False,
    }
    write_json(args.report.resolve(), report)
    print("MICHIGAN_GAMEPLAY_INSTALL_STATUS=installed")
    print(f"MICHIGAN_GAMEPLAY_INSTALL_FILES={len(candidate_hashes)}")
    print(f"MICHIGAN_GAMEPLAY_INSTALL_ARCHIVE={archive}")
    print(f"MICHIGAN_GAMEPLAY_INSTALL_REPORT={args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
