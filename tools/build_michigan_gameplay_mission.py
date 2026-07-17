#!/usr/bin/env python3
"""Build a clean MichiganMitten mission candidate around generated CE files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


COPY_DIRECTORIES = ("custom", "db", "EditorFiles", "env")
FORBIDDEN_PART_PREFIXES = ("storage_", "_backup", "_storage")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def is_runtime_artifact(relative: Path) -> bool:
    lowered = [part.lower() for part in relative.parts]
    if any(part.startswith(FORBIDDEN_PART_PREFIXES) for part in lowered):
        return True
    return relative.name.lower() in {"players.db", "spawnpoints.bin"} or relative.suffix.lower() == ".log"


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-mission", required=True, type=Path)
    parser.add_argument("--ce-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    base = args.base_mission.resolve()
    ce_dir = args.ce_dir.resolve()
    output = args.out_dir.resolve()
    if not base.is_dir():
        raise SystemExit(f"Base mission does not exist: {base}")
    if not ce_dir.is_dir():
        raise SystemExit(f"CE directory does not exist: {ce_dir}")
    if output == base or output == ce_dir or output.parent == output:
        raise SystemExit(f"Unsafe output directory: {output}")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    copied_from_base: list[str] = []
    excluded: list[str] = []
    for entry in sorted(base.iterdir(), key=lambda item: item.name.lower()):
        relative = Path(entry.name)
        if entry.is_file():
            if is_runtime_artifact(relative) or entry.name.startswith("_backup"):
                excluded.append(relative.as_posix())
                continue
            copy_file(entry, output / relative)
            copied_from_base.append(relative.as_posix())
            continue
        if entry.name not in COPY_DIRECTORIES:
            excluded.append(relative.as_posix() + "/")
            continue
        for source in sorted(entry.rglob("*")):
            if not source.is_file():
                continue
            nested = source.relative_to(base)
            if is_runtime_artifact(nested):
                excluded.append(nested.as_posix())
                continue
            copy_file(source, output / nested)
            copied_from_base.append(nested.as_posix())

    overlaid: list[str] = []
    for source in sorted(ce_dir.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(ce_dir)
        if is_runtime_artifact(relative):
            raise SystemExit(f"CE overlay contains runtime artifact: {relative}")
        copy_file(source, output / relative)
        overlaid.append(relative.as_posix())

    files = sorted(path for path in output.rglob("*") if path.is_file())
    hashes = {path.relative_to(output).as_posix(): sha256(path) for path in files}
    report = {
        "status": "built",
        "baseMission": str(base),
        "ceDirectory": str(ce_dir),
        "outputMission": str(output),
        "fileCount": len(files),
        "totalBytes": sum(path.stat().st_size for path in files),
        "baseFileCount": len(copied_from_base),
        "ceOverlayFileCount": len(overlaid),
        "ceOverlayFiles": overlaid,
        "excludedEntries": excluded,
        "sha256": hashes,
    }
    write_json(args.report.resolve(), report)
    print("MICHIGAN_MISSION_BUILD_STATUS=built")
    print(f"MICHIGAN_MISSION_FILES={len(files)}")
    print(f"MICHIGAN_MISSION_CE_OVERLAY={len(overlaid)}")
    print(f"MICHIGAN_MISSION_OUTPUT={output}")
    print(f"MICHIGAN_MISSION_REPORT={args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
