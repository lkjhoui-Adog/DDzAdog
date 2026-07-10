#!/usr/bin/env python3
"""Build a minimal DayZ WRP height grid from an ESRI ASC heightmap."""

from __future__ import annotations

import argparse
import math
import re
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


def write_surface_indices(
    handle,
    width: int,
    height: int,
    material_paths: list[str],
    surface_tile_count: int | None,
    flip_y: bool,
) -> None:
    if surface_tile_count is None:
        handle.write(b"\x01\x00" * (width * height))
        return

    if surface_tile_count <= 0:
        raise ValueError("--surface-tile-count must be positive")
    if width % surface_tile_count or height % surface_tile_count:
        raise ValueError(
            f"Surface grid {width}x{height} must be divisible by "
            f"--surface-tile-count {surface_tile_count}"
        )

    material_indices: dict[tuple[int, int], int] = {}
    for index, material_path in enumerate(material_paths, start=1):
        name = material_path.rsplit("\\", 1)[-1]
        match = re.fullmatch(r"P_(\d{3})-(\d{3})_L00\.rvmat", name, flags=re.IGNORECASE)
        if match:
            material_indices[(int(match.group(1)), int(match.group(2)))] = index

    expected = {
        (tile_x, tile_y)
        for tile_x in range(surface_tile_count)
        for tile_y in range(surface_tile_count)
    }
    missing = sorted(expected - material_indices.keys())
    if missing:
        raise ValueError(f"Missing tiled L00 surface materials: {missing[:8]}")

    cells_per_tile_x = width // surface_tile_count
    rows_per_tile_y = height // surface_tile_count
    for tile_y in range(surface_tile_count):
        material_y = surface_tile_count - 1 - tile_y if flip_y else tile_y
        row = b"".join(
            struct.pack("<H", material_indices[(tile_x, material_y)]) * cells_per_tile_x
            for tile_x in range(surface_tile_count)
        )
        handle.write(row * rows_per_tile_y)


def write_surface_tail(
    handle,
    width: int,
    height: int,
    material_paths: list[str],
    surface_tile_count: int | None,
    flip_y: bool,
) -> None:
    if not material_paths:
        raise ValueError("At least one surface material path is required")

    # Material index 0 is the reserved empty entry.
    write_surface_indices(handle, width, height, material_paths, surface_tile_count, flip_y)
    handle.write(struct.pack("<II", len(material_paths) + 1, 0))
    for material_path in material_paths:
        material = material_path.encode("ascii")
        handle.write(struct.pack("<I", len(material)))
        handle.write(material)
        handle.write(struct.pack("<I", 0))
    handle.write(WRP_FINAL_SURFACE_RECORD)


def collect_material_paths(
    surface_material: str | None,
    surface_materials_dir: Path | None,
    material_prefix: str | None,
) -> list[str]:
    if surface_materials_dir is None:
        return [surface_material] if surface_material else []

    if not material_prefix:
        raise ValueError("--surface-material-prefix is required with --surface-materials-dir")

    material_dir = surface_materials_dir.resolve()
    if not material_dir.is_dir():
        raise ValueError(f"--surface-materials-dir is not a directory: {material_dir}")

    paths = [
        f"{material_prefix.rstrip('\\/')}\\{path.name}"
        for path in sorted(material_dir.glob("P_*.rvmat"), key=lambda item: item.name.lower())
    ]
    if not paths:
        raise ValueError(f"No P_*.rvmat files found in {material_dir}")
    return paths


def build_with_numpy(
    input_asc: Path,
    output_wrp: Path,
    header: dict[str, float],
    target_size: int | None,
    texture_grid_size: int | None,
    cell_size: float,
    material_paths: list[str],
    surface_tile_count: int | None,
    flip_y: bool,
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

    # ESRI ASCII rows run north-to-south; WRP rows run south-to-north.
    if flip_y:
        data = data[::-1].copy()

    texture_width = texture_grid_size or ncols
    texture_height = texture_grid_size or nrows
    if texture_width <= 0 or texture_height <= 0:
        raise ValueError("--texture-grid-size must be a positive integer")
    if ncols % texture_width != 0 or nrows % texture_height != 0:
        raise ValueError(
            f"Terrain grid {ncols}x{nrows} must be evenly divisible by "
            f"texture grid {texture_width}x{texture_height}"
        )

    tmp = output_wrp.with_suffix(output_wrp.suffix + ".tmp")
    with tmp.open("wb") as handle:
        handle.write(b"0WZD")
        # WRP stores texture-grid dimensions first and terrain-grid dimensions second.
        handle.write(struct.pack("<iiii", texture_width, texture_height, ncols, nrows))
        handle.write(struct.pack("<f", cell_size))
        data.tofile(handle)
        if material_paths:
            write_surface_tail(handle, texture_width, texture_height, material_paths, surface_tile_count, flip_y)
    tmp.replace(output_wrp)

    return {
        "samples": int(data.size),
        "min": float(np.nanmin(data)),
        "max": float(np.nanmax(data)),
        "mean": float(np.nanmean(data)),
        "texture_grid_size": texture_width,
        "cell_size": cell_size,
    }


def build_streaming(
    input_asc: Path,
    output_wrp: Path,
    header: dict[str, float],
    target_size: int | None,
    texture_grid_size: int | None,
    cell_size: float,
    material_paths: list[str],
    surface_tile_count: int | None,
    flip_y: bool,
) -> dict[str, float]:
    from array import array

    if target_size is not None:
        raise ModuleNotFoundError("Downsampling requires numpy")

    ncols = int(header["ncols"])
    nrows = int(header["nrows"])
    texture_width = texture_grid_size or ncols
    texture_height = texture_grid_size or nrows
    if texture_width <= 0 or texture_height <= 0:
        raise ValueError("--texture-grid-size must be a positive integer")
    if ncols % texture_width != 0 or nrows % texture_height != 0:
        raise ValueError(
            f"Terrain grid {ncols}x{nrows} must be evenly divisible by "
            f"texture grid {texture_width}x{texture_height}"
        )
    nodata = float(header.get("nodata_value", -9999.0))
    samples = 0
    min_value = math.inf
    max_value = -math.inf
    total = 0.0
    tmp = output_wrp.with_suffix(output_wrp.suffix + ".tmp")

    with input_asc.open("r", encoding="ascii", errors="strict") as source, tmp.open("wb") as target:
        for _ in range(6):
            source.readline()
        target.write(b"0WZD")
        target.write(struct.pack("<iiii", texture_width, texture_height, ncols, nrows))
        target.write(struct.pack("<f", cell_size))

        rows: list[array] = []
        for row_index, line in enumerate(source, start=1):
            values = []
            for token in line.split():
                value = float(token)
                if value == nodata:
                    value = 0.0
                values.append(value)
                samples += 1
                total += value
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
            if flip_y:
                rows.append(floats)
            else:
                floats.tofile(target)

        if flip_y:
            for floats in reversed(rows):
                floats.tofile(target)

        if material_paths:
            write_surface_tail(target, texture_width, texture_height, material_paths, surface_tile_count, flip_y)

    if samples != ncols * nrows:
        raise ValueError(f"ASC contained {samples} samples; expected {ncols * nrows}")
    tmp.replace(output_wrp)
    return {
        "samples": samples,
        "min": min_value,
        "max": max_value,
        "mean": total / samples,
        "texture_grid_size": texture_width,
        "cell_size": cell_size,
    }


def inspect_wrp(path: Path) -> dict[str, int | float]:
    with path.open("rb") as handle:
        magic = handle.read(4)
        if magic != b"0WZD":
            raise ValueError(f"{path} does not start with a 0WZD header")
        texture_width, texture_height, terrain_width, terrain_height = struct.unpack("<iiii", handle.read(16))
        cell_size = struct.unpack("<f", handle.read(4))[0]
    return {
        "texture_width": texture_width,
        "texture_height": texture_height,
        "terrain_width": terrain_width,
        "terrain_height": terrain_height,
        "cell_size": cell_size,
        "terrain_cell_size": cell_size * texture_width / terrain_width,
    }


def resolve_cell_size(
    header: dict[str, float],
    target_size: int | None,
    texture_grid_size: int | None,
    explicit_cell_size: float | None,
) -> float:
    if explicit_cell_size is not None:
        if explicit_cell_size <= 0:
            raise ValueError("--cell-size must be positive")
        return explicit_cell_size

    source_terrain_cell_size = float(header.get("cellsize", 0.0))
    if source_terrain_cell_size <= 0:
        raise ValueError("ASC header must include a positive cellsize or --cell-size must be supplied")
    source_size = int(header["ncols"])
    terrain_grid_size = target_size or source_size
    texture_size = texture_grid_size or terrain_grid_size
    if terrain_grid_size <= 0 or source_size % terrain_grid_size != 0:
        raise ValueError(f"Cannot derive cell size while downsampling {source_size} columns to {terrain_grid_size}")
    if texture_size <= 0 or terrain_grid_size % texture_size != 0:
        raise ValueError(
            f"Terrain grid {terrain_grid_size} must be evenly divisible by texture grid {texture_size}"
        )

    world_size = source_size * source_terrain_cell_size
    return world_size / texture_size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-asc", required=True, type=Path)
    parser.add_argument("--output-wrp", required=True, type=Path)
    parser.add_argument("--backup-existing", action="store_true")
    parser.add_argument("--target-size", type=int, help="Optionally downsample the square ASC grid before writing WRP")
    parser.add_argument(
        "--texture-grid-size",
        type=int,
        help="Texture/material grid width. For a 2048 terrain grid with 20 m cells and 80 m texture layers, use 512.",
    )
    parser.add_argument(
        "--cell-size",
        type=float,
        help=(
            "WRP texture-grid cell size in meters. Defaults to the ASC world size divided by "
            "--texture-grid-size; a 40.96 km world with a 512 texture grid uses 80 m."
        ),
    )
    parser.add_argument(
        "--surface-material",
        help="Optional WRP material path to fill the surface index grid, for example MichiganMitten\\data\\layers\\P_000-000_L00.rvmat",
    )
    parser.add_argument(
        "--surface-materials-dir",
        type=Path,
        help="Optional folder of P_*.rvmat files to embed in the WRP material table",
    )
    parser.add_argument(
        "--surface-material-prefix",
        help="PBO path prefix to use with --surface-materials-dir, for example MichiganMitten\\data\\layers",
    )
    parser.add_argument(
        "--surface-tile-count",
        type=int,
        help="Map a square set of P_XXX-YYY_L00 materials across the WRP surface grid",
    )
    parser.add_argument(
        "--flip-y",
        action="store_true",
        help="Flip north-first ESRI ASC rows into the south-first row order used by WRP",
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

    material_paths = collect_material_paths(args.surface_material, args.surface_materials_dir, args.surface_material_prefix)
    cell_size = resolve_cell_size(header, args.target_size, args.texture_grid_size, args.cell_size)

    try:
        stats = build_with_numpy(
            input_asc,
            output_wrp,
            header,
            args.target_size,
            args.texture_grid_size,
            cell_size,
            material_paths,
            args.surface_tile_count,
            args.flip_y,
        )
        mode = "numpy"
    except ModuleNotFoundError:
        stats = build_streaming(
            input_asc,
            output_wrp,
            header,
            args.target_size,
            args.texture_grid_size,
            cell_size,
            material_paths,
            args.surface_tile_count,
            args.flip_y,
        )
        mode = "streaming"

    wrp = inspect_wrp(output_wrp)
    print(f"mode={mode}")
    print(f"output={output_wrp}")
    print(
        f"texture_grid={wrp['texture_width']}x{wrp['texture_height']} "
        f"terrain_grid={wrp['terrain_width']}x{wrp['terrain_height']} "
        f"texture_cell_size={wrp['cell_size']:.3f} "
        f"terrain_cell_size={wrp['terrain_cell_size']:.3f}"
    )
    print(f"samples={stats['samples']} min={stats['min']:.3f} max={stats['max']:.3f} mean={stats['mean']:.3f}")
    print(f"surface_materials={len(material_paths)}")
    print(f"surface_tile_count={args.surface_tile_count or 0}")
    print(f"flip_y={int(args.flip_y)}")
    print(f"bytes={output_wrp.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
