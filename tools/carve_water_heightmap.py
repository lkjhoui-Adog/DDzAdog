import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
EXPORT_ROOT = ROOT / "terrain" / "exports" / "utm16n"
META_FILE = EXPORT_ROOT / "terrain_builder_export_metadata.json"
SOURCE_DIR = ROOT / "terrain" / "terrain-builder" / "MichiganSurvival" / "source"
WORKDRIVE_SOURCE_DIR = ROOT / "workdrive" / "MichiganSurvival" / "source"
SOURCE_ASC = SOURCE_DIR / "michigan_survival_height_4096.asc"


def project_path(value):
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_asc(path):
    header = {}
    header_lines = []
    with path.open("r", encoding="ascii") as f:
        for _ in range(6):
            line = f.readline().strip()
            header_lines.append(line)
            key, value = line.split(maxsplit=1)
            header[key.lower()] = value
        arr = np.loadtxt(f, dtype=np.float32)
    return header, header_lines, arr


def write_asc(path, header_lines, arr):
    nodata = float((line.split(maxsplit=1)[1] for line in header_lines if line.lower().startswith("nodata_value")).__next__())

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="\n") as f:
        for line in header_lines:
            f.write(f"{line}\n")
        for row in arr:
            f.write(" ".join(f"{value:.3f}" if np.isfinite(value) else f"{nodata:g}" for value in row))
            f.write("\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Normalize and carve water areas in a Terrain Builder ASC heightmap.")
    parser.add_argument("--export-root", default=str(EXPORT_ROOT))
    parser.add_argument("--package-root", default=None)
    parser.add_argument("--workdrive-root", default=None)
    parser.add_argument("--road-floor", type=float, default=5.0)
    parser.add_argument("--road-buffer-pixels", type=int, default=2)
    return parser.parse_args()


def configure_from_args(args, meta):
    global EXPORT_ROOT, META_FILE, SOURCE_DIR, WORKDRIVE_SOURCE_DIR, SOURCE_ASC
    EXPORT_ROOT = project_path(args.export_root)
    META_FILE = EXPORT_ROOT / "terrain_builder_export_metadata.json"
    package_root = project_path(args.package_root) if args.package_root else ROOT / "terrain" / "terrain-builder" / meta["terrainName"]
    workdrive_root = project_path(args.workdrive_root) if args.workdrive_root else ROOT / "workdrive" / meta["terrainName"]
    SOURCE_DIR = package_root / "source"
    WORKDRIVE_SOURCE_DIR = workdrive_root / "source"
    SOURCE_ASC = SOURCE_DIR / f"{meta['outputPrefix']}_height_{meta['heightmap']['rasterSize']}.asc"


def main():
    args = parse_args()
    meta = read_json(project_path(args.export_root) / "terrain_builder_export_metadata.json")
    configure_from_args(args, meta)
    water_mask_path = ROOT / meta["masks"]["water"]["path"]
    road_mask_path = ROOT / meta["masks"]["roads"]["path"]

    if args.road_floor <= 0:
        raise ValueError("--road-floor must be positive")
    if args.road_buffer_pixels < 0:
        raise ValueError("--road-buffer-pixels cannot be negative")

    header, header_lines, heights = read_asc(SOURCE_ASC)
    valid = np.isfinite(heights)
    nodata = float(header.get("nodata_value", "-9999"))
    valid &= heights != nodata
    water_mask = np.array(Image.open(water_mask_path).convert("L")) > 0
    road_mask_image = Image.open(road_mask_path).convert("L")
    road_mask = np.array(road_mask_image) > 0
    if args.road_buffer_pixels:
        filter_size = args.road_buffer_pixels * 2 + 1
        road_corridor = np.array(road_mask_image.filter(ImageFilter.MaxFilter(size=filter_size))) > 0
    else:
        road_corridor = road_mask

    # Road geometry is not useful when its terrain cells are at the waterline.
    # Treat the buffered corridor as land, including short causeways across water.
    effective_water_mask = water_mask & ~road_corridor

    if np.any(valid & water_mask):
        water_level = float(np.nanpercentile(heights[valid & water_mask], 35))
    else:
        water_level = float(np.nanpercentile(heights[valid], 5))
    normalized = heights - water_level

    below_water = np.full_like(normalized, -6.0)
    water_soft = np.array(
        Image.fromarray((effective_water_mask.astype(np.uint8) * 255), mode="L").filter(
            ImageFilter.GaussianBlur(radius=5)
        )
    ).astype(np.float32) / 255.0
    carved = normalized * (1.0 - water_soft) + below_water * water_soft

    shore = (water_soft > 0.02) & (water_soft < 0.92)
    carved[shore] = np.minimum(carved[shore], 1.25)
    carved[effective_water_mask] = np.minimum(carved[effective_water_mask], -2.0)
    land = valid & ~effective_water_mask
    carved[land] = np.maximum(carved[land], 0.35)

    road_soft = np.array(
        Image.fromarray((road_corridor.astype(np.uint8) * 255), mode="L").filter(
            ImageFilter.GaussianBlur(radius=max(1, args.road_buffer_pixels + 1))
        )
    ).astype(np.float32) / 255.0
    road_shoulder_floor = 0.35 + road_soft * (args.road_floor - 0.35)
    carved[land] = np.maximum(carved[land], road_shoulder_floor[land])
    carved[valid & road_corridor] = np.maximum(carved[valid & road_corridor], args.road_floor)
    carved[~valid] = np.nan

    out_name = f"{meta['outputPrefix']}_height_{meta['heightmap']['rasterSize']}_water_carved.asc"
    for out_dir in (SOURCE_DIR, WORKDRIVE_SOURCE_DIR):
        write_asc(out_dir / out_name, header_lines, carved)

    preview = carved.copy()
    preview[~np.isfinite(preview)] = np.nanmin(preview[np.isfinite(preview)])
    preview = np.clip((preview - np.nanmin(preview)) / (np.nanmax(preview) - np.nanmin(preview)) * 255, 0, 255).astype(np.uint8)
    for out_dir in (SOURCE_DIR, WORKDRIVE_SOURCE_DIR):
        Image.fromarray(preview, mode="L").save(out_dir / f"{meta['outputPrefix']}_height_{meta['heightmap']['rasterSize']}_water_carved_preview.png")

    report = {
        "sourceAsc": str(SOURCE_ASC),
        "sourceWaterMask": str(water_mask_path),
        "sourceRoadMask": str(road_mask_path),
        "waterLevelSubtractedMeters": water_level,
        "roadFloorMeters": args.road_floor,
        "roadBufferPixels": args.road_buffer_pixels,
        "roadCorridorPixels": int(np.count_nonzero(road_corridor)),
        "waterPixelsProtectedByRoads": int(np.count_nonzero(water_mask & road_corridor)),
        "outputAsc": out_name,
        "carvedElevationMeters": {
            "min": float(np.nanmin(carved)),
            "max": float(np.nanmax(carved)),
            "waterPixelMax": (
                float(np.nanmax(carved[effective_water_mask])) if np.any(effective_water_mask) else None
            ),
            "landPixelMin": float(np.nanmin(carved[land])),
            "roadPixelMin": float(np.nanmin(carved[valid & road_mask])),
        },
    }
    for out_dir in (SOURCE_DIR, WORKDRIVE_SOURCE_DIR):
        (out_dir / "water_carve_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Water level subtracted: {water_level:.3f} m")
    print(f"Wrote {SOURCE_DIR / out_name}")
    print(f"Wrote {WORKDRIVE_SOURCE_DIR / out_name}")


if __name__ == "__main__":
    main()
