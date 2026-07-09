import argparse
import json
import re
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
import rasterio.warp
from PIL import Image, ImageFilter
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.merge import merge
from rasterio.transform import from_origin
from shapely.geometry import LineString, MultiLineString, Polygon, box, mapping, shape
from shapely.ops import transform as shapely_transform


ROOT = Path(__file__).resolve().parents[1]
BOUNDS_FILE = ROOT / "source-data" / "prototype-bounds.json"
DOWNLOADS = ROOT / "source-data" / "downloads"
RAW_ELEVATION = ROOT / "source-data" / "raw" / "elevation"
TIGER_GEOJSON = ROOT / "source-data" / "raw" / "tiger" / "geojson"
GIS_DIR = ROOT / "terrain" / "gis"
EXPORT_ROOT = ROOT / "terrain" / "exports" / "utm16n"
SIZE = 4096
CRS_WGS84 = "EPSG:4326"
CRS_PROJECT = "EPSG:32616"
OSM_FILE = DOWNLOADS / "traverse-city-osm-roads-water.json"
OUTPUT_PREFIX = "michigan_survival_traverse_10km_utm16n"
PROJECT_LABEL = "MichiganSurvival Traverse City 10km"
SURFACE_PREFS = {}


def project_path(value):
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


def slugify(value):
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return slug or "terrain"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_geojson(path, features, crs_name=CRS_WGS84):
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        path,
        {
            "type": "FeatureCollection",
            "name": path.stem,
            "crs": {"type": "name", "properties": {"name": crs_name}},
            "features": features,
        },
    )


def select_latest_dem_items(items):
    selected = {}
    for item in items:
        url = item.get("downloadURL")
        if not url:
            continue
        title = item.get("title", "")
        match = re.search(r"n\d+w\d+", title.lower())
        key = match.group(0) if match else Path(url.split("?")[0]).stem
        previous = selected.get(key)
        if previous is None or item.get("lastUpdated", "") > previous.get("lastUpdated", ""):
            selected[key] = item
    return sorted(selected.values(), key=lambda item: item.get("title", ""))


def download_dem_paths():
    RAW_ELEVATION.mkdir(parents=True, exist_ok=True)
    existing = sorted(RAW_ELEVATION.glob("*.tif"))
    if existing:
        return existing

    products = read_json(DOWNLOADS / "usgs-tnm-dem-products.json")
    items = select_latest_dem_items(products.get("items", []))
    if not items:
        raise RuntimeError("No USGS DEM downloadURL found.")

    out_paths = []
    for item in items:
        url = item["downloadURL"]
        out = RAW_ELEVATION / Path(url.split("?")[0]).name
        print(f"Downloading DEM: {url}")
        urllib.request.urlretrieve(url, out)
        out_paths.append(out)
    return out_paths


def empty_layers():
    return {name: [] for name in ["roads", "waterways", "water_polygons", "woods", "landuse"]}


def tiger_to_features():
    layers = empty_layers()
    sources = {
        "roads": TIGER_GEOJSON / "tiger_roads.geojson",
        "water_polygons": TIGER_GEOJSON / "tiger_areawater.geojson",
        "waterways": TIGER_GEOJSON / "tiger_linearwater.geojson",
    }
    if not all(path.exists() for path in sources.values()):
        return None

    for layer_name, path in sources.items():
        data = read_json(path)
        for feature in data.get("features", []):
            props = feature.get("properties") or {}
            geom = shape(feature["geometry"])
            if layer_name == "roads":
                props["highway"] = "primary" if props.get("MTFCC") in {"S1100", "S1200"} else "residential"
            if layer_name == "water_polygons":
                props["natural"] = "water"
            if layer_name == "waterways":
                props["waterway"] = "stream"
            layers[layer_name].append({"type": "Feature", "properties": props, "geometry": mapping(geom)})

    for name, features in layers.items():
        write_geojson(GIS_DIR / f"{name}.geojson", features)

    return layers


def osm_to_features():
    osm = read_json(OSM_FILE)
    nodes = {}
    ways = []
    for el in osm.get("elements", []):
        if el.get("type") == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])
        elif el.get("type") == "way":
            ways.append(el)

    layers = empty_layers()

    for way in ways:
        coords = [nodes[node_id] for node_id in way.get("nodes", []) if node_id in nodes]
        if len(coords) < 2:
            continue
        tags = way.get("tags", {})
        props = dict(tags)

        geom = None
        is_closed = len(coords) > 3 and coords[0] == coords[-1]
        if is_closed:
            try:
                geom = Polygon(coords)
                if not geom.is_valid:
                    geom = geom.buffer(0)
            except Exception:
                geom = None
        if geom is None:
            geom = LineString(coords)

        feature = {"type": "Feature", "properties": props, "geometry": mapping(geom)}

        if "highway" in tags:
            layers["roads"].append(feature)
        if "waterway" in tags:
            layers["waterways"].append(feature)
        if tags.get("natural") == "water" or "water" in tags:
            if isinstance(geom, Polygon):
                layers["water_polygons"].append(feature)
        if tags.get("natural") == "wood" or tags.get("landuse") == "forest":
            if isinstance(geom, Polygon):
                layers["woods"].append(feature)
        if "landuse" in tags and isinstance(geom, Polygon):
            layers["landuse"].append(feature)

    for name, features in layers.items():
        write_geojson(GIS_DIR / f"{name}.geojson", features)

    return layers


def transform_feature(feature, transformer):
    geom = shape(feature["geometry"])
    projected = shapely_transform(transformer.transform, geom)
    return {"type": "Feature", "properties": feature["properties"], "geometry": mapping(projected)}


def project_and_clip_layers(layers, bounds_projected, transformer):
    out = {}
    for name, features in layers.items():
        projected = []
        for feature in features:
            geom = shape(transform_feature(feature, transformer)["geometry"])
            clipped = geom.intersection(bounds_projected)
            if clipped.is_empty:
                continue
            projected.append({"type": "Feature", "properties": feature["properties"], "geometry": mapping(clipped)})
        out[name] = projected
        write_geojson(EXPORT_ROOT / "vectors" / f"{name}_clipped.geojson", projected, CRS_PROJECT)
        write_geojson(EXPORT_ROOT / "vectors" / f"{name}_utm16n_clipped.geojson", projected, CRS_PROJECT)
    write_geojson(
        EXPORT_ROOT / "vectors" / "prototype_bounds.geojson",
        [{"type": "Feature", "properties": {"name": f"{PROJECT_LABEL} Bounds"}, "geometry": mapping(bounds_projected)}],
        CRS_PROJECT,
    )
    write_geojson(
        EXPORT_ROOT / "vectors" / "prototype_bounds_utm16n.geojson",
        [{"type": "Feature", "properties": {"name": f"{PROJECT_LABEL} Bounds"}, "geometry": mapping(bounds_projected)}],
        CRS_PROJECT,
    )
    return out


def export_heightmap(dem_paths, bounds_projected):
    height_dir = EXPORT_ROOT / "heightmap"
    height_dir.mkdir(parents=True, exist_ok=True)

    minx, miny, maxx, maxy = bounds_projected.bounds
    pixel_size = (maxx - minx) / SIZE
    dst_transform = from_origin(minx, maxy, pixel_size, pixel_size)
    dst = np.full((SIZE, SIZE), np.nan, dtype=np.float32)

    sources = [rasterio.open(path) for path in dem_paths]
    try:
        if len(sources) == 1:
            source = rasterio.band(sources[0], 1)
            src_transform = sources[0].transform
            src_crs = sources[0].crs
        else:
            mosaic, src_transform = merge(sources)
            source = mosaic[0]
            src_crs = sources[0].crs

        rasterio.warp.reproject(
            source=source,
            destination=dst,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=dst_transform,
            dst_crs=CRS_PROJECT,
            resampling=Resampling.bilinear,
            dst_nodata=np.nan,
        )
    finally:
        for src in sources:
            src.close()

    dst = np.where(dst < 0, np.nan, dst)
    valid = np.isfinite(dst)
    if not np.any(valid):
        raise RuntimeError("DEM export produced no valid height samples for the selected bounds.")

    min_m = float(np.nanmin(dst[valid]))
    max_m = float(np.nanmax(dst[valid]))
    height16 = np.zeros_like(dst, dtype=np.uint16)
    height16[valid] = ((dst[valid] - min_m) / (max_m - min_m) * 65535.0).clip(0, 65535).astype(np.uint16)

    png_path = height_dir / f"{OUTPUT_PREFIX}_height_{SIZE}.png"
    preview_path = height_dir / f"{OUTPUT_PREFIX}_height_preview.png"
    tif_path = height_dir / f"{OUTPUT_PREFIX}_float.tif"

    Image.fromarray(height16, mode="I;16").save(png_path)
    preview = ((height16.astype(np.float32) / 65535.0) * 255).astype(np.uint8)
    Image.fromarray(preview, mode="L").save(preview_path)

    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        height=SIZE,
        width=SIZE,
        count=1,
        dtype="float32",
        crs=CRS_PROJECT,
        transform=dst_transform,
        nodata=np.nan,
    ) as dst_file:
        dst_file.write(dst, 1)

    return {
        "floatTiff": str(tif_path.relative_to(ROOT)).replace("\\", "/"),
        "heightPng16": str(png_path.relative_to(ROOT)).replace("\\", "/"),
        "previewPng": str(preview_path.relative_to(ROOT)).replace("\\", "/"),
        "rasterSize": SIZE,
        "pixelSizeMeters": pixel_size,
        "elevationMeters": {"min": min_m, "max": max_m, "range": max_m - min_m},
        "transform": [dst_transform.a, dst_transform.b, dst_transform.c, dst_transform.d, dst_transform.e, dst_transform.f],
    }, dst_transform


def export_masks(projected_layers, transform):
    masks_dir = EXPORT_ROOT / "masks"
    masks_dir.mkdir(parents=True, exist_ok=True)

    def procedural_forest_mask():
        rng = np.random.default_rng(1776)
        coarse_size = max(16, SIZE // 64)
        coarse = (rng.random((coarse_size, coarse_size)) * 255).astype(np.uint8)
        image = Image.fromarray(coarse, mode="L").resize((SIZE, SIZE), Image.Resampling.BILINEAR)
        image = image.filter(ImageFilter.GaussianBlur(radius=max(12, SIZE // 128)))
        noise = np.array(image)
        threshold = 128 if SURFACE_PREFS.get("forestBias") == "high" else 152
        return (noise > threshold).astype(np.uint8) * 255

    def save_mask(name, geoms):
        valid_geoms = [(geom, 255) for geom in geoms if not geom.is_empty]
        if valid_geoms:
            mask = rasterize(valid_geoms, out_shape=(SIZE, SIZE), transform=transform, fill=0, dtype=np.uint8)
        elif name == "woods" and SURFACE_PREFS.get("forestBias") in {"high", "moderate"}:
            mask = procedural_forest_mask()
        else:
            mask = np.zeros((SIZE, SIZE), dtype=np.uint8)
        path = masks_dir / f"{name}_mask_{SIZE}.png"
        tif_path = masks_dir / f"{name}_mask_{SIZE}.tif"
        Image.fromarray(mask, mode="L").save(path)
        with rasterio.open(
            tif_path,
            "w",
            driver="GTiff",
            height=SIZE,
            width=SIZE,
            count=1,
            dtype="uint8",
            crs=CRS_PROJECT,
            transform=transform,
            nodata=0,
        ) as dst_file:
            dst_file.write(mask, 1)
        return {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "geoTiff": str(tif_path.relative_to(ROOT)).replace("\\", "/"),
            "nonzeroPixels": int(np.count_nonzero(mask)),
        }

    water_geoms = [shape(f["geometry"]) for f in projected_layers["water_polygons"]]
    water_geoms.extend(
        [
            shape(f["geometry"]).buffer(4)
            for f in projected_layers["waterways"]
            if isinstance(shape(f["geometry"]), (LineString, MultiLineString))
        ]
    )
    woods_geoms = [shape(f["geometry"]) for f in projected_layers["woods"]]
    roads_geoms = []
    for f in projected_layers["roads"]:
        geom = shape(f["geometry"])
        kind = f["properties"].get("highway", "")
        width = 8 if kind in {"motorway", "trunk", "primary", "secondary"} else 4
        roads_geoms.append(geom.buffer(width))
    farmland_geoms = [
        shape(f["geometry"])
        for f in projected_layers["landuse"]
        if f["properties"].get("landuse") in {"farmland", "farmyard", "meadow", "orchard"}
    ]
    urban_geoms = [
        shape(f["geometry"])
        for f in projected_layers["landuse"]
        if f["properties"].get("landuse") in {"residential", "industrial", "commercial", "retail"}
    ]

    masks = {}
    for name, geoms in {
        "water": water_geoms,
        "woods": woods_geoms,
        "roads": roads_geoms,
        "farmland": farmland_geoms,
        "urban": urban_geoms,
    }.items():
        masks[name] = save_mask(name, geoms)
    return masks


def parse_args():
    parser = argparse.ArgumentParser(description="Process DayZ terrain source data into height/mask/vector exports.")
    parser.add_argument("--bounds-file", default=str(BOUNDS_FILE))
    parser.add_argument("--downloads-dir", default=str(DOWNLOADS))
    parser.add_argument("--raw-elevation-dir", default=str(RAW_ELEVATION))
    parser.add_argument("--tiger-geojson-dir", default=str(TIGER_GEOJSON))
    parser.add_argument("--gis-dir", default=str(GIS_DIR))
    parser.add_argument("--export-root", default=str(EXPORT_ROOT))
    parser.add_argument("--osm-file", default=None)
    parser.add_argument("--heightmap-size", type=int, default=SIZE)
    return parser.parse_args()


def configure_from_args(args, bounds):
    global BOUNDS_FILE, DOWNLOADS, RAW_ELEVATION, TIGER_GEOJSON, GIS_DIR
    global EXPORT_ROOT, SIZE, CRS_PROJECT, OSM_FILE, OUTPUT_PREFIX, PROJECT_LABEL, SURFACE_PREFS

    BOUNDS_FILE = project_path(args.bounds_file)
    DOWNLOADS = project_path(args.downloads_dir)
    RAW_ELEVATION = project_path(args.raw_elevation_dir)
    TIGER_GEOJSON = project_path(args.tiger_geojson_dir)
    GIS_DIR = project_path(args.gis_dir)
    EXPORT_ROOT = project_path(args.export_root)
    SIZE = args.heightmap_size
    CRS_PROJECT = bounds.get("targetCrs") or bounds.get("crs") or CRS_PROJECT
    OUTPUT_PREFIX = bounds.get("outputPrefix") or slugify(f"{bounds['terrainName']}_{bounds['prototypeName']}")
    PROJECT_LABEL = bounds.get("prototypeName") or bounds["terrainName"]
    SURFACE_PREFS = bounds.get("surfacePreferences", {})
    OSM_FILE = project_path(args.osm_file) if args.osm_file else DOWNLOADS / bounds.get("osmFile", "traverse-city-osm-roads-water.json")


def main():
    args = parse_args()
    bounds = read_json(project_path(args.bounds_file))
    configure_from_args(args, bounds)

    dem_paths = download_dem_paths()
    layers = tiger_to_features()
    if layers is None:
        layers = osm_to_features()

    to_project = Transformer.from_crs(CRS_WGS84, CRS_PROJECT, always_xy=True)
    center_e, center_n = to_project.transform(bounds["center"]["longitude"], bounds["center"]["latitude"])
    half = bounds["sizeKm"] * 1000 / 2
    bounds_projected = box(center_e - half, center_n - half, center_e + half, center_n + half)

    projected_layers = project_and_clip_layers(layers, bounds_projected, to_project)
    height_meta, dst_transform = export_heightmap(dem_paths, bounds_projected)
    masks = export_masks(projected_layers, dst_transform)

    metadata = {
        "terrainName": bounds["terrainName"],
        "prototypeName": bounds["prototypeName"],
        "outputPrefix": OUTPUT_PREFIX,
        "crs": CRS_PROJECT,
        "sizeMeters": bounds["sizeKm"] * 1000,
        "centerWgs84": bounds["center"],
        "centerProjected": {"easting": center_e, "northing": center_n},
        "centerUtm16n": {"easting": center_e, "northing": center_n},
        "boundsProjected": {
            "west": bounds_projected.bounds[0],
            "south": bounds_projected.bounds[1],
            "east": bounds_projected.bounds[2],
            "north": bounds_projected.bounds[3],
        },
        "boundsUtm16n": {
            "west": bounds_projected.bounds[0],
            "south": bounds_projected.bounds[1],
            "east": bounds_projected.bounds[2],
            "north": bounds_projected.bounds[3],
        },
        "heightmap": height_meta,
        "masks": masks,
        "names": bounds.get("names", []),
        "vectorLayerFeatureCounts": {name: len(features) for name, features in projected_layers.items()},
        "sourceFiles": {
            "bounds": str(BOUNDS_FILE.relative_to(ROOT)).replace("\\", "/") if BOUNDS_FILE.is_relative_to(ROOT) else str(BOUNDS_FILE),
            "downloads": str(DOWNLOADS.relative_to(ROOT)).replace("\\", "/") if DOWNLOADS.is_relative_to(ROOT) else str(DOWNLOADS),
            "dems": [str(path.relative_to(ROOT)).replace("\\", "/") if path.is_relative_to(ROOT) else str(path) for path in dem_paths],
            "osm": str(OSM_FILE.relative_to(ROOT)).replace("\\", "/") if OSM_FILE.exists() and OSM_FILE.is_relative_to(ROOT) else str(OSM_FILE),
        },
    }
    write_json(EXPORT_ROOT / "terrain_builder_export_metadata.json", metadata)
    print("Processed source data.")
    print(f"DEM files: {len(dem_paths)}")
    print(f"Metadata: {EXPORT_ROOT / 'terrain_builder_export_metadata.json'}")


if __name__ == "__main__":
    main()
