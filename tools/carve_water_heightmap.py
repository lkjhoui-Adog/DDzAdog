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


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


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


def main():
    meta = read_json(META_FILE)
    water_mask_path = ROOT / meta["masks"]["water"]["path"]

    header, header_lines, heights = read_asc(SOURCE_ASC)
    valid = np.isfinite(heights)
    nodata = float(header.get("nodata_value", "-9999"))
    valid &= heights != nodata
    water_mask = np.array(Image.open(water_mask_path).convert("L")) > 0

    # Lake Michigan / Grand Traverse Bay sits at the low end of this DEM. Normalize
    # the terrain so actual water is near DayZ sea level instead of 176m above it.
    water_level = float(np.nanpercentile(heights[valid & water_mask], 35))
    normalized = heights - water_level

    below_water = np.full_like(normalized, -6.0)
    water_soft = np.array(
        Image.fromarray((water_mask.astype(np.uint8) * 255), mode="L")
        .filter(ImageFilter.GaussianBlur(radius=5))
    ).astype(np.float32) / 255.0
    carved = normalized * (1.0 - water_soft) + below_water * water_soft

    # Keep a shallow shoreline instead of hard 170m cliffs where the DEM waterline
    # was noisy. Land remains above sea level; masked water is swimmable.
    shore = (water_soft > 0.02) & (water_soft < 0.92)
    carved[shore] = np.minimum(carved[shore], 1.25)
    carved[water_mask] = np.minimum(carved[water_mask], -2.0)
    carved[valid & ~water_mask] = np.maximum(carved[valid & ~water_mask], 0.35)
    carved[~valid] = np.nan

    out_name = "michigan_survival_height_4096_water_carved.asc"
    for out_dir in (SOURCE_DIR, WORKDRIVE_SOURCE_DIR):
        write_asc(out_dir / out_name, header_lines, carved)

    preview = carved.copy()
    preview[~np.isfinite(preview)] = np.nanmin(preview[np.isfinite(preview)])
    preview = np.clip((preview - np.nanmin(preview)) / (np.nanmax(preview) - np.nanmin(preview)) * 255, 0, 255).astype(np.uint8)
    for out_dir in (SOURCE_DIR, WORKDRIVE_SOURCE_DIR):
        Image.fromarray(preview, mode="L").save(out_dir / "michigan_survival_height_4096_water_carved_preview.png")

    report = {
        "sourceAsc": str(SOURCE_ASC),
        "sourceWaterMask": str(water_mask_path),
        "waterLevelSubtractedMeters": water_level,
        "outputAsc": out_name,
        "carvedElevationMeters": {
            "min": float(np.nanmin(carved)),
            "max": float(np.nanmax(carved)),
            "waterPixelMax": float(np.nanmax(carved[water_mask])),
            "landPixelMin": float(np.nanmin(carved[valid & ~water_mask])),
        },
    }
    for out_dir in (SOURCE_DIR, WORKDRIVE_SOURCE_DIR):
        (out_dir / "water_carve_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Water level subtracted: {water_level:.3f} m")
    print(f"Wrote {SOURCE_DIR / out_name}")
    print(f"Wrote {WORKDRIVE_SOURCE_DIR / out_name}")


if __name__ == "__main__":
    main()
