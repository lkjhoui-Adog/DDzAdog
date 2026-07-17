#!/usr/bin/env python3
"""Generate the tiled 2D map overlay used by DayZ's MapWidget."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
EXPORT_ROOT = ROOT / "terrain" / "exports" / "michigan-lower-peninsula"
DEFAULT_ROADS = (
    ROOT
    / "build"
    / "candidates"
    / "statewide-road-population-20260712-pass1"
    / "statewide-population-roads-world.geojson"
)
DEFAULT_HEIGHTMAP = EXPORT_ROOT / "heightmap" / "michigan_mitten_height_4096.png"
DEFAULT_OUTPUT = ROOT / "workdrive" / "MichiganMitten-Statewide" / "data" / "usermap"
DEFAULT_PREVIEW = ROOT / "build" / "diagnostics" / "michigan-mitten-usermap-preview.png"
DEFAULT_REPORT = ROOT / "build" / "diagnostics" / "michigan-mitten-usermap-report.json"
DEFAULT_CONVERTER = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools\Bin\ImageToPAA\ImageToPAA.exe"
)
WORLD_SIZE = 40960.0
RASTER_SIZE = 4096
TILE_GRID = 32
TILE_SIZE = 512

ROAD_STYLES = {
    "freeway": {"casing": (67, 70, 68), "fill": (230, 177, 69), "outer": 6, "inner": 4},
    "rural": {"casing": (78, 81, 78), "fill": (243, 225, 154), "outer": 5, "inner": 3},
    "urban": {"casing": (88, 91, 89), "fill": (229, 226, 216), "outer": 4, "inner": 2},
    "local": {"casing": (113, 116, 112), "fill": (245, 243, 235), "outer": 2, "inner": 1},
    "dirt": {"casing": (103, 84, 59), "fill": (197, 164, 111), "outer": 4, "inner": 2},
    "bridge": {"casing": (48, 53, 54), "fill": (238, 228, 190), "outer": 7, "inner": 4},
}


def load_mask(name: str) -> np.ndarray:
    path = EXPORT_ROOT / "masks" / f"{name}_mask_{RASTER_SIZE}.png"
    if not path.exists():
        raise FileNotFoundError(path)
    return np.asarray(Image.open(path).convert("L")) > 0


def geometry_lines(geometry: dict) -> list[list[list[float]]]:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates", [])
    if geometry_type == "LineString":
        return [coordinates]
    if geometry_type == "MultiLineString":
        return coordinates
    return []


def world_to_pixel(point: list[float]) -> tuple[int, int]:
    x = round(float(point[0]) * (RASTER_SIZE - 1) / WORLD_SIZE)
    y = round((WORLD_SIZE - float(point[1])) * (RASTER_SIZE - 1) / WORLD_SIZE)
    return x, y


def road_style(properties: dict) -> str:
    model = str(properties.get("model", ""))
    highway = str(properties.get("highway", ""))
    if properties.get("scope") == "bridge-deck":
        return "bridge"
    if "Dirt" in model or properties.get("surface") == "dirt":
        return "dirt"
    if "Freeway" in model:
        return "freeway"
    if "Rural" in model or properties.get("scope") == "regional":
        return "rural"
    if "Urban" in model or highway == "tertiary":
        return "urban"
    return "local"


def load_road_lines(path: Path) -> dict[str, list[list[tuple[int, int]]]]:
    roads = {style: [] for style in ROAD_STYLES}
    data = json.loads(path.read_text(encoding="utf-8"))
    for feature in data.get("features", []):
        style = road_style(feature.get("properties", {}))
        for line in geometry_lines(feature.get("geometry", {})):
            pixels = [world_to_pixel(point) for point in line]
            if len(pixels) >= 2:
                roads[style].append(pixels)
    return roads


def load_lines(path: Path) -> list[list[tuple[int, int]]]:
    lines: list[list[tuple[int, int]]] = []
    data = json.loads(path.read_text(encoding="utf-8"))
    for feature in data.get("features", []):
        for line in geometry_lines(feature.get("geometry", {})):
            pixels = [world_to_pixel(point) for point in line]
            if len(pixels) >= 2:
                lines.append(pixels)
    return lines


def apply_hillshade(image: np.ndarray, heightmap_path: Path, land: np.ndarray) -> None:
    height = np.asarray(Image.open(heightmap_path), dtype=np.float32)
    if height.shape != land.shape:
        raise RuntimeError(f"Heightmap dimensions {height.shape} do not match {land.shape}.")

    height /= max(float(height.max()), 1.0)
    gradient_y, gradient_x = np.gradient(height)
    directional = (gradient_x * -0.72) + (gradient_y * 0.69)
    scale = float(np.percentile(np.abs(directional[land]), 99.2))
    if scale <= 0:
        return

    shade = np.clip(directional / scale, -1.0, 1.0) * 13.0
    shaded = image.astype(np.int16)
    shaded[land] = np.clip(shaded[land] + shade[land, None], 0, 255)
    image[:] = shaded.astype(np.uint8)


def draw_road_network(
    draw: ImageDraw.ImageDraw, road_lines: dict[str, list[list[tuple[int, int]]]]
) -> None:
    # Draw lower-priority roads first so state routes and freeways remain legible.
    for style_name in ("local", "dirt", "urban", "rural", "freeway", "bridge"):
        style = ROAD_STYLES[style_name]
        for line in road_lines[style_name]:
            draw.line(line, fill=style["casing"], width=style["outer"], joint="curve")
        for line in road_lines[style_name]:
            draw.line(line, fill=style["fill"], width=style["inner"], joint="curve")


def build_map_image(roads_path: Path, heightmap_path: Path) -> tuple[Image.Image, dict[str, int]]:
    water = load_mask("water")
    woods = load_mask("woods")
    farmland = load_mask("farmland")
    urban = load_mask("urban")
    mitten = load_mask("mitten")

    image = np.empty((RASTER_SIZE, RASTER_SIZE, 3), dtype=np.uint8)
    image[:, :] = (226, 232, 220)
    image[mitten] = (215, 226, 205)
    image[woods & ~water] = (177, 204, 169)
    image[farmland & ~water] = (230, 220, 184)
    image[urban & ~water] = (205, 204, 196)
    image[water] = (178, 207, 228)

    land = mitten & ~water
    apply_hillshade(image, heightmap_path, land)

    coast_source = Image.fromarray((water.astype(np.uint8) * 255), mode="L")
    coast_outer = np.asarray(coast_source.filter(ImageFilter.MaxFilter(3))) > 0
    coast_inner = np.asarray(coast_source.filter(ImageFilter.MinFilter(3))) > 0
    image[coast_outer ^ coast_inner] = (73, 118, 147)

    result = Image.fromarray(image, mode="RGB")
    draw = ImageDraw.Draw(result)
    road_lines = load_road_lines(roads_path)
    draw_road_network(draw, road_lines)

    counts = {style: len(lines) for style, lines in road_lines.items()}
    return result, counts


def convert_tile(converter: Path, png: Path, paa: Path) -> None:
    completed = subprocess.run(
        [str(converter), str(png), str(paa)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0 or not paa.exists():
        raise RuntimeError(f"ImageToPAA failed for {png.name}: {completed.stderr.strip()}")


def generate_tiles(image: Image.Image, output: Path, converter: Path, workers: int) -> None:
    source_tile_size = RASTER_SIZE // TILE_GRID
    if source_tile_size * TILE_GRID != RASTER_SIZE:
        raise RuntimeError("Raster size must divide evenly into the user-map tile grid.")

    output.mkdir(parents=True, exist_ok=True)
    for old_tile in output.glob("s_*_*_lco.paa"):
        old_tile.unlink()

    with tempfile.TemporaryDirectory(prefix="michigan-usermap-") as temp_name:
        temp = Path(temp_name)
        jobs: list[tuple[Path, Path]] = []
        for row in range(TILE_GRID):
            for column in range(TILE_GRID):
                left = column * source_tile_size
                top = row * source_tile_size
                tile = image.crop((left, top, left + source_tile_size, top + source_tile_size))
                tile = tile.resize((TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS)
                tile = tile.filter(ImageFilter.UnsharpMask(radius=0.8, percent=80, threshold=2))
                stem = f"s_{column:03d}_{row:03d}_lco"
                png = temp / f"{stem}.png"
                paa = output / f"{stem}.paa"
                tile.save(png, optimize=True)
                jobs.append((png, paa))

        completed_count = 0
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {
                executor.submit(convert_tile, converter, png, paa): paa for png, paa in jobs
            }
            for future in as_completed(futures):
                future.result()
                completed_count += 1
                if completed_count % 128 == 0:
                    print(f"Converted {completed_count}/{len(jobs)} map tiles.", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--preview", type=Path, default=DEFAULT_PREVIEW)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--roads", type=Path, default=DEFAULT_ROADS)
    parser.add_argument("--heightmap", type=Path, default=DEFAULT_HEIGHTMAP)
    parser.add_argument("--converter", type=Path, default=DEFAULT_CONVERTER)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--preview-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.roads.exists():
        raise FileNotFoundError(args.roads)
    if not args.heightmap.exists():
        raise FileNotFoundError(args.heightmap)
    image, line_counts = build_map_image(args.roads, args.heightmap)

    args.preview.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.preview, optimize=True)

    if not args.preview_only:
        if not args.converter.exists():
            raise FileNotFoundError(args.converter)
        generate_tiles(image, args.output, args.converter, args.workers)

    report = {
        "worldSizeMeters": WORLD_SIZE,
        "sourceRasterSize": RASTER_SIZE,
        "tileGrid": TILE_GRID,
        "tileSize": TILE_SIZE,
        "tileCount": 0 if args.preview_only else TILE_GRID * TILE_GRID,
        "output": str(args.output),
        "preview": str(args.preview),
        "roadSource": str(args.roads),
        "heightmapSource": str(args.heightmap),
        "vectorLineCounts": line_counts,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
