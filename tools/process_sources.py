import json
import math
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
import rasterio.warp
from PIL import Image, ImageFilter
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import LineString, MultiLineString, Polygon, shape, mapping, box
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
CRS_UTM16N = "EPSG:32616"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_geojson(path, features, crs_name=CRS_WGS84):
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, {
        "type": "FeatureCollection",
        "name": path.stem,
        "crs": {"type": "name", "properties": {"name": crs_name}},
        "features": features,
    })


def download_dem():
    RAW_ELEVATION.mkdir(parents=True, exist_ok=True)
    existing = sorted(RAW_ELEVATION.glob("*.tif"))
    if existing:
        return existing[0]

    products = read_json(DOWNLOADS / "usgs-tnm-dem-products.json")
    items = [item for item in products.get("items", []) if item.get("downloadURL")]
    if not items:
        raise RuntimeError("No USGS DEM downloadURL found.")

    selected = sorted(items, key=lambda item: item.get("lastUpdated", ""), reverse=True)[0]
    url = selected["downloadURL"]
    out = RAW_ELEVATION / Path(url.split("?")[0]).name
    print(f"Downloading DEM: {url}")
    urllib.request.urlretrieve(url, out)
    return out


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
    osm = read_json(DOWNLOADS / "traverse-city-osm-roads-water.json")
    nodes = {}
    ways = []
    relations = []
    for el in osm.get("elements", []):
        if el.get("type") == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])
        elif el.get("type") == "way":
            ways.append(el)
        elif el.get("type") == "relation":
            relations.append(el)

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
        write_geojson(EXPORT_ROOT / "vectors" / f"{name}_utm16n_clipped.geojson", projected, CRS_UTM16N)
    write_geojson(EXPORT_ROOT / "vectors" / "prototype_bounds_utm16n.geojson", [{
        "type": "Feature",
        "properties": {"name": "MichiganSurvival Traverse City 10km UTM Bounds"},
        "geometry": mapping(bounds_projected),
    }], CRS_UTM16N)
    return out


def export_heightmap(dem_path, bounds_projected):
    height_dir = EXPORT_ROOT / "heightmap"
    height_dir.mkdir(parents=True, exist_ok=True)

    minx, miny, maxx, maxy = bounds_projected.bounds
    pixel_size = (maxx - minx) / SIZE
    dst_transform = from_origin(minx, maxy, pixel_size, pixel_size)
    dst = np.zeros((SIZE, SIZE), dtype=np.float32)

    with rasterio.open(dem_path) as src:
        rasterio.warp.reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=CRS_UTM16N,
            resampling=Resampling.bilinear,
            dst_nodata=np.nan,
        )

    valid = np.isfinite(dst)
    min_m = float(np.nanmin(dst[valid]))
    max_m = float(np.nanmax(dst[valid]))
    height16 = ((dst - min_m) / (max_m - min_m) * 65535.0).clip(0, 65535).astype(np.uint16)
    height16[~valid] = 0

    png_path = height_dir / "michigan_survival_traverse_10km_utm16n_height_4096.png"
    preview_path = height_dir / "michigan_survival_traverse_10km_utm16n_height_preview.png"
    tif_path = height_dir / "michigan_survival_traverse_10km_utm16n_float.tif"

    Image.fromarray(height16, mode="I;16").save(png_path)
    preview = ((height16.astype(np.float32) / 65535.0) * 255).astype(np.uint8)
    Image.fromarray(preview, mode="L").save(preview_path)

    with rasterio.open(
        tif_path, "w", driver="GTiff", height=SIZE, width=SIZE, count=1, dtype="float32",
        crs=CRS_UTM16N, transform=dst_transform, nodata=np.nan
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

    def save_mask(name, geoms):
        if geoms:
            mask = rasterize([(geom, 255) for geom in geoms if not geom.is_empty], out_shape=(SIZE, SIZE), transform=transform, fill=0, dtype=np.uint8)
        else:
            mask = np.zeros((SIZE, SIZE), dtype=np.uint8)
        path = masks_dir / f"{name}_mask_4096.png"
        tif_path = masks_dir / f"{name}_mask_4096_utm16n.tif"
        Image.fromarray(mask, mode="L").save(path)
        with rasterio.open(
            tif_path, "w", driver="GTiff", height=SIZE, width=SIZE, count=1, dtype="uint8",
            crs=CRS_UTM16N, transform=transform, nodata=0
        ) as dst_file:
            dst_file.write(mask, 1)
        return {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "geoTiff": str(tif_path.relative_to(ROOT)).replace("\\", "/"),
            "nonzeroPixels": int(np.count_nonzero(mask)),
        }

    water_geoms = [shape(f["geometry"]) for f in projected_layers["water_polygons"]]
    water_geoms.extend([
        shape(f["geometry"]).buffer(4)
        for f in projected_layers["waterways"]
        if isinstance(shape(f["geometry"]), (LineString, MultiLineString))
    ])
    woods_geoms = [shape(f["geometry"]) for f in projected_layers["woods"]]
    roads_geoms = []
    for f in projected_layers["roads"]:
        geom = shape(f["geometry"])
        kind = f["properties"].get("highway", "")
        width = 6 if kind in {"motorway", "trunk", "primary", "secondary"} else 3
        roads_geoms.append(geom.buffer(width))
    farmland_geoms = [shape(f["geometry"]) for f in projected_layers["landuse"] if f["properties"].get("landuse") in {"farmland", "farmyard", "meadow", "orchard"}]
    urban_geoms = [shape(f["geometry"]) for f in projected_layers["landuse"] if f["properties"].get("landuse") in {"residential", "industrial", "commercial", "retail"}]

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


def main():
    bounds = read_json(BOUNDS_FILE)
    dem_path = download_dem()
    layers = tiger_to_features()
    if layers is None:
        layers = osm_to_features()

    to_utm = Transformer.from_crs(CRS_WGS84, CRS_UTM16N, always_xy=True)
    center_e, center_n = to_utm.transform(bounds["center"]["longitude"], bounds["center"]["latitude"])
    half = bounds["sizeKm"] * 1000 / 2
    bounds_projected = box(center_e - half, center_n - half, center_e + half, center_n + half)

    projected_layers = project_and_clip_layers(layers, bounds_projected, to_utm)
    height_meta, dst_transform = export_heightmap(dem_path, bounds_projected)
    masks = export_masks(projected_layers, dst_transform)

    metadata = {
        "terrainName": bounds["terrainName"],
        "prototypeName": bounds["prototypeName"],
        "crs": CRS_UTM16N,
        "sizeMeters": bounds["sizeKm"] * 1000,
        "centerWgs84": bounds["center"],
        "centerUtm16n": {"easting": center_e, "northing": center_n},
        "boundsUtm16n": {
            "west": bounds_projected.bounds[0],
            "south": bounds_projected.bounds[1],
            "east": bounds_projected.bounds[2],
            "north": bounds_projected.bounds[3],
        },
        "heightmap": height_meta,
        "masks": masks,
        "vectorLayerFeatureCounts": {name: len(features) for name, features in projected_layers.items()},
    }
    write_json(EXPORT_ROOT / "terrain_builder_export_metadata.json", metadata)
    print("Processed source data.")
    print(f"DEM: {dem_path}")
    print(f"Metadata: {EXPORT_ROOT / 'terrain_builder_export_metadata.json'}")


if __name__ == "__main__":
    main()
