#!/usr/bin/env python3
"""Build a minimal DayZ WRP height grid from an ESRI ASC heightmap."""

from __future__ import annotations

import argparse
import math
import shutil
import struct
from pathlib import Path

WRP_FINAL_SURFACE_RECORD = bytes.fromhex(
    "88 7f c8 7f 88 7f c8 7f 88 7f c8 7f 88 7f c8 7f "
    "88 7f c8 7f 88 7f c8 7f 88 7f c8 7f 88 7f c8 7f "
    "88 7f c8 7f 88 7f c8 7f 88 7f c8 7f 88 7f c8 7f "
    "70 42 24 01 00 00 00 00"
)


def read_header(path: Path) -> tuple[dict[str, float], int]:
    header: dict[str, float] = {}
    lines = 0
    with path.open("r", encoding="ascii", errors="strict") as handle:
        for _ in range(6):
            line = handle.readline()
            if not line:
                raise ValueError(f"{path} ended before the ASC header was complete")
            lines += 1
            key, value = line.strip().split(maxsplit=1)
            key = key.lower()
            if key in {"ncols", "nrows"}:
                header[key] = int(value)
            else:
                header[key] = float(value)
    for key in ("ncols", "nrows"):
        if key not in header:
            raise ValueError(f"{path} is missing ASC header key {key}")
    return header, lines


def write_surface_tail(handle, width: int, height: int, material_path: str) -> None:
    material = material_path.encode("ascii")
    handle.write(b"\x00\x00" * (width * height))
    handle.write(struct.pack("<II", 2, 0))
    handle.write(struct.pack("<I", len(material)))
    handle.write(material)
    handle.write(struct.pack("<I", 0))
    handle.write(WRP_FINAL_SURFACE_RECORD)


def build_with_numpy(
    input_asc: Path,
    output_wrp: Path,
    header: dict[str, float],
    target_size: int | None,
    material_path: str | None,
) -> dict[str, float]:
    import numpy as np

    ncols = int(header["ncols"])
    nrows = int(header["nrows"])
    nodata = float(header.get("nodata_value", -9999.0))
    data = np.loadtxt(input_asc, skiprows=6, dtype="<f4")
    if data.shape != (nrows, ncols):
        raise ValueError(f"Expected ASC data shape {(nrows, ncols)}, got {data.shape}")
    if np.isfinite(nodata):
        data = np.where(data == nodata, 0.0, data).astype("<f4", copy=False)
    if target_size is not None and target_size != ncols:
        if target_size <= 0:
            raise ValueError("--target-size must be a positive integer")
        if ncols % target_size != 0:
            raise ValueError(f"Cannot evenly downsample {ncols} columns to {target_size}")
        factor = ncols // target_size
        data = data.reshape(target_size, factor, target_size, factor).mean(axis=(1, 3)).astype("<f4")
        ncols = target_size
        nrows = target_size

    tmp = output_wrp.with_suffix(output_wrp.suffix + ".tmp")
    with tmp.open("wb") as handle:
        handle.write(b"0WZD")
        handle.write(struct.pack("<iiii", ncols, nrows, ncols, nrows))
        data.tofile(handle)
        if material_path:
            handle.write(struct.pack("<f", float(data.ravel()[-1])))
            write_surface_tail(handle, ncols, nrows, material_path)
    tmp.replace(output_wrp)

    return {
        "samples": int(data.size),
        "min": float(np.nanmin(data)),
        "max": float(np.nanmax(data)),
        "mean": float(np.nanmean(data)),
    }


def build_streaming(
    input_asc: Path,
    output_wrp: Path,
    header: dict[str, float],
    target_size: int | None,
    material_path: str | None,
) -> dict[str, float]:
    from array import array

    if target_size is not None:
        raise ModuleNotFoundError("Downsampling requires numpy")

    ncols = int(header["ncols"])
    nrows = int(header["nrows"])
    nodata = float(header.get("nodata_value", -9999.0))
    samples = 0
    min_value = math.inf
    max_value = -math.inf
    total = 0.0
    last_value = 0.0
    tmp = output_wrp.with_suffix(output_wrp.suffix + ".tmp")

    with input_asc.open("r", encoding="ascii", errors="strict") as source, tmp.open("wb") as target:
        for _ in range(6):
            source.readline()
        target.write(b"0WZD")
        target.write(struct.pack("<iiii", ncols, nrows, ncols, nrows))

        for row_index, line in enumerate(source, start=1):
            values = []
            for token in line.split():
                value = float(token)
                if value == nodata:
                    value = 0.0
                values.append(value)
                samples += 1
                total += value
                last_value = value
                if value < min_value:
                    min_value = value
                if value > max_value:
                    max_value = value
            if len(values) != ncols:
                raise ValueError(f"ASC row {row_index} has {len(values)} columns; expected {ncols}")
            floats = array("f", values)
            if floats.itemsize != 4:
                raise RuntimeError("This Python runtime does not use 32-bit array('f') values")
            if struct.pack("=f", 1.0) != struct.pack("<f", 1.0):
                floats.byteswap()
            floats.tofile(target)

        if material_path:
            target.write(struct.pack("<f", last_value))
            write_surface_tail(target, ncols, nrows, material_path)

    if samples != ncols * nrows:
        raise ValueError(f"ASC contained {samples} samples; expected {ncols * nrows}")
    tmp.replace(output_wrp)
    return {"samples": samples, "min": min_value, "max": max_value, "mean": total / samples}


def inspect_wrp(path: Path) -> dict[str, int]:
    with path.open("rb") as handle:
        magic = handle.read(4)
        if magic != b"0WZD":
            raise ValueError(f"{path} does not start with a 0WZD header")
        width, height, width2, height2 = struct.unpack("<iiii", handle.read(16))
    return {"width": width, "height": height, "width2": width2, "height2": height2}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-asc", required=True, type=Path)
    parser.add_argument("--output-wrp", required=True, type=Path)
    parser.add_argument("--backup-existing", action="store_true")
    parser.add_argument("--target-size", type=int, help="Optionally downsample the square ASC grid before writing WRP")
    parser.add_argument(
        "--surface-material",
        help="Optional WRP material path to fill the surface index grid, for example MichiganMitten\\data\\layers\\P_000-000_L00.rvmat",
    )
    args = parser.parse_args()

    input_asc = args.input_asc.resolve()
    output_wrp = args.output_wrp.resolve()
    output_wrp.parent.mkdir(parents=True, exist_ok=True)

    header, _ = read_header(input_asc)
    if int(header["ncols"]) != int(header["nrows"]):
        raise ValueError(f"ASC must be square for this terrain: {header['ncols']} x {header['nrows']}")

    if args.backup_existing and output_wrp.exists():
        backup = output_wrp.with_suffix(output_wrp.suffix + ".before-minimal-rebuild.bak")
        shutil.copy2(output_wrp, backup)
        print(f"backup={backup}")

    try:
        stats = build_with_numpy(input_asc, output_wrp, header, args.target_size, args.surface_material)
        mode = "numpy"
    except ModuleNotFoundError:
        stats = build_streaming(input_asc, output_wrp, header, args.target_size, args.surface_material)
        mode = "streaming"

    wrp = inspect_wrp(output_wrp)
    print(f"mode={mode}")
    print(f"output={output_wrp}")
    print(f"dimensions={wrp['width']}x{wrp['height']} secondary={wrp['width2']}x{wrp['height2']}")
    print(f"samples={stats['samples']} min={stats['min']:.3f} max={stats['max']:.3f} mean={stats['mean']:.3f}")
    print(f"bytes={output_wrp.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
