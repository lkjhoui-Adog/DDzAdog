import argparse
import concurrent.futures
import json
import math
import re
import shutil
import urllib.request
from pathlib import Path

import fiona
import numpy as np
import rasterio
import rasterio.warp
from PIL import Image, ImageFilter
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.ndimage import distance_transform_edt
from shapely import make_valid, prepare, union_all
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon, box, mapping, shape
from shapely.ops import transform as shapely_transform


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "source-data" / "michigan-lower-peninsula-40960.json"
DEFAULT_GPKG = ROOT / "source-data" / "raw" / "osm" / "michigan-lower-peninsula.gpkg"
DEFAULT_DEM_META = ROOT / "source-data" / "downloads" / "michigan-lower-peninsula" / "usgs-tnm-dem-products.json"
DEFAULT_DEM_DIR = ROOT / "source-data" / "raw" / "elevation" / "michigan-lower-peninsula"
DEFAULT_EXPORT = ROOT / "terrain" / "exports" / "michigan-lower-peninsula"

ROAD_CLASSES = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
}
HOMETOWN_CLASSES = ROAD_CLASSES | {"tertiary", "tertiary_link"}
ROAD_WIDTHS = {
    "motorway": 9.0,
    "motorway_link": 6.0,
    "trunk": 8.0,
    "trunk_link": 6.0,
    "primary": 7.0,
    "primary_link": 5.0,
    "secondary": 6.0,
    "secondary_link": 5.0,
    "tertiary": 5.0,
    "tertiary_link": 4.0,
    "residential": 4.0,
    "unclassified": 4.0,
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def clean_geometry(geom):
    if geom is None or geom.is_empty:
        return None
    if not geom.is_valid:
        geom = make_valid(geom)
    if geom.is_empty:
        return None
    return geom


def polygon_parts(geom):
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    if isinstance(geom, GeometryCollection):
        result = []
        for part in geom.geoms:
            result.extend(polygon_parts(part))
        return result
    return []


def densified_wgs84_box(bounds, steps=64):
    west = bounds["west"]
    south = bounds["south"]
    east = bounds["east"]
    north = bounds["north"]
    coords = []
    for index in range(steps):
        t = index / steps
        coords.append((west + (east - west) * t, south))
    for index in range(steps):
        t = index / steps
        coords.append((east, south + (north - south) * t))
    for index in range(steps):
        t = index / steps
        coords.append((east - (east - west) * t, north))
    for index in range(steps):
        t = index / steps
        coords.append((west, north - (north - south) * t))
    coords.append(coords[0])
    return Polygon(coords)


def latest_dem_items(metadata):
    selected = {}
    for item in metadata.get("items", []):
        url = item.get("downloadURL")
        title = item.get("title", "")
        match = re.search(r"n\d+w\d+", title.lower())
        if not url or not match:
            continue
        key = match.group(0)
        previous = selected.get(key)
        if previous is None or item.get("lastUpdated", "") > previous.get("lastUpdated", ""):
            selected[key] = item
    return [selected[key] for key in sorted(selected)]


def download_one_dem(item, output_dir):
    url = item["downloadURL"]
    output = output_dir / Path(url.split("?")[0]).name
    if output.exists() and output.stat().st_size > 1_000_000:
        return output
    temporary = output.with_suffix(output.suffix + ".part")
    print(f"Downloading DEM {output.name}")
    urllib.request.urlretrieve(url, temporary)
    temporary.replace(output)
    return output


def ensure_dem_files(metadata_path, output_dir, workers=4):
    output_dir.mkdir(parents=True, exist_ok=True)
    items = latest_dem_items(read_json(metadata_path))
    if not items:
        raise RuntimeError(f"No tiled DEM downloads found in {metadata_path}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        paths = list(executor.map(lambda item: download_one_dem(item, output_dir), items))
    return sorted(paths)


def iter_layer(path, layer):
    with fiona.open(path, layer=layer) as source:
        for feature in source:
            geometry = feature.get("geometry")
            if geometry is None:
                continue
            yield dict(feature.get("properties") or {}), shape(geometry)


def osm_other_tag(properties, key):
    text = properties.get("other_tags") or ""
    match = re.search(rf'"{re.escape(key)}"=>"([^"]*)"', text)
    return match.group(1) if match else None


def build_land_geometry(config, gpkg_path, to_working):
    source_frame = shapely_transform(
        to_working.transform,
        densified_wgs84_box(config["sourceBoundsWgs84"]),
    )
    lake_names = set(config["greatLakes"])
    lake_geometries = []
    for properties, geometry in iter_layer(gpkg_path, "polygons"):
        if properties.get("natural") != "water" or properties.get("name") not in lake_names:
            continue
        projected = clean_geometry(shapely_transform(to_working.transform, geometry))
        if projected is not None and projected.intersects(source_frame):
            lake_geometries.append(projected.intersection(source_frame))
    if not lake_geometries:
        raise RuntimeError("No Great Lakes polygons were found in the statewide OSM extract.")

    great_lakes = clean_geometry(union_all(lake_geometries))
    state_geometries = []
    for properties, geometry in iter_layer(gpkg_path, "michigan_boundary"):
        projected = clean_geometry(shapely_transform(to_working.transform, geometry))
        if projected is not None:
            state_geometries.append(projected)
    if not state_geometries:
        raise RuntimeError("The Michigan administrative boundary is missing from the OSM extract.")
    state_boundary = clean_geometry(union_all(state_geometries).intersection(source_frame))
    candidates = clean_geometry(state_boundary.difference(great_lakes))
    lansing = Point(*to_working.transform(-84.5555, 42.7325))
    parts = polygon_parts(candidates)
    containing = [part for part in parts if part.covers(lansing)]
    if not containing:
        raise RuntimeError("Could not isolate the Lower Peninsula land component.")
    mainland = max(containing, key=lambda part: part.area)
    return clean_geometry(mainland), source_frame, great_lakes, state_boundary


def build_world_mapping(config, land_geometry):
    world_size = float(config["worldSizeMeters"])
    padding = config["worldPaddingMeters"]
    minx, miny, maxx, maxy = land_geometry.bounds
    width = maxx - minx
    height = maxy - miny
    available_height = world_size - float(padding["bottom"]) - float(padding["top"])
    available_width = world_size - 2.0 * float(padding["minimumSide"])
    scale = min(available_height / height, available_width / width)
    land_width_world = width * scale
    land_height_world = height * scale
    offset_x = (world_size - land_width_world) / 2.0
    offset_y = float(padding["bottom"])
    top_padding = world_size - (offset_y + land_height_world)
    if top_padding + 0.01 < float(padding["top"]):
        raise RuntimeError("Configured map padding does not fit the Lower Peninsula.")
    return {
        "sourceLandBounds": [minx, miny, maxx, maxy],
        "scale": scale,
        "realMetersPerGameMeter": 1.0 / scale,
        "offsetX": offset_x,
        "offsetY": offset_y,
        "topPadding": top_padding,
    }


def world_transformer(mapping_info):
    minx, miny, _, _ = mapping_info["sourceLandBounds"]
    scale = mapping_info["scale"]
    offset_x = mapping_info["offsetX"]
    offset_y = mapping_info["offsetY"]

    def project(x, y, z=None):
        world_x = (np.asarray(x) - minx) * scale + offset_x
        world_y = (np.asarray(y) - miny) * scale + offset_y
        if z is None:
            return world_x, world_y
        return world_x, world_y, z

    return project


def transform_bounds_polygon(bounds_wgs84, to_working):
    return shapely_transform(to_working.transform, densified_wgs84_box(bounds_wgs84, steps=16))


def build_road_features(config, gpkg_path, to_working, to_world, land_projected):
    prepare(land_projected)
    major_features = []
    major_ids = set()
    for properties, geometry in iter_layer(gpkg_path, "major_roads"):
        highway = properties.get("highway") or ""
        if highway not in ROAD_CLASSES:
            continue
        projected = clean_geometry(shapely_transform(to_working.transform, geometry))
        if projected is None or not projected.intersects(land_projected):
            continue
        world_geometry = clean_geometry(shapely_transform(to_world, projected).simplify(1.5, preserve_topology=False))
        if world_geometry is None:
            continue
        osm_id = str(properties.get("osm_id") or "")
        major_ids.add(osm_id)
        major_features.append(
            {
                "properties": {
                    "osm_id": osm_id,
                    "name": properties.get("name"),
                    "highway": highway,
                    "ref": osm_other_tag(properties, "ref"),
                    "bridge": osm_other_tag(properties, "bridge"),
                    "lanes": osm_other_tag(properties, "lanes"),
                    "oneway": osm_other_tag(properties, "oneway"),
                    "source": "statewide-major",
                },
                "geometry": world_geometry,
            }
        )

    hometown = config["hometown"]
    hometown_bounds = transform_bounds_polygon(hometown["boundsWgs84"], to_working)
    wanted_names = {name.casefold() for name in hometown["roadNames"]}
    hometown_features = []
    seen = set()
    for properties, geometry in iter_layer(gpkg_path, "hometown_roads"):
        highway = properties.get("highway") or ""
        name = properties.get("name") or ""
        normalized_name = name.casefold()
        named_corridor = normalized_name in wanted_names or normalized_name.replace("northbound ", "").replace("southbound ", "") in wanted_names
        if highway not in HOMETOWN_CLASSES and not named_corridor:
            continue
        projected = clean_geometry(shapely_transform(to_working.transform, geometry))
        if projected is None or not projected.intersects(hometown_bounds):
            continue
        projected = clean_geometry(projected.intersection(hometown_bounds))
        if projected is None:
            continue
        osm_id = str(properties.get("osm_id") or "")
        key = (osm_id, name, highway)
        if key in seen or (osm_id in major_ids and highway in ROAD_CLASSES):
            continue
        seen.add(key)
        world_geometry = clean_geometry(shapely_transform(to_world, projected).simplify(0.75, preserve_topology=False))
        if world_geometry is None:
            continue
        hometown_features.append(
            {
                "properties": {
                    "osm_id": osm_id,
                    "name": name or None,
                    "highway": highway,
                    "ref": osm_other_tag(properties, "ref"),
                    "bridge": osm_other_tag(properties, "bridge"),
                    "lanes": osm_other_tag(properties, "lanes"),
                    "oneway": osm_other_tag(properties, "oneway"),
                    "source": "hometown-detail",
                },
                "geometry": world_geometry,
            }
        )
    return major_features, hometown_features


def build_navigation_waterways(config, gpkg_path, to_working, to_world):
    wanted_names = set(config["navigableWaterways"]["names"])
    features = []
    for properties, geometry in iter_layer(gpkg_path, "southeast_waterways"):
        name = properties.get("name") or ""
        if name not in wanted_names:
            continue
        projected = clean_geometry(shapely_transform(to_working.transform, geometry))
        if projected is None:
            continue
        world_geometry = clean_geometry(shapely_transform(to_world, projected).simplify(1.0, preserve_topology=False))
        if world_geometry is not None:
            features.append(
                {
                    "properties": {"name": name, "waterway": properties.get("waterway") or "river"},
                    "geometry": world_geometry,
                }
            )
    return features


def navigation_water_mask(config, features, raster_size, transform):
    half_width = float(config["navigableWaterways"]["minimumWidthGameMeters"]) / 2.0
    buffered = []
    for feature in features:
        geometry = clean_geometry(feature["geometry"].buffer(half_width, cap_style="round", join_style="round"))
        if geometry is not None:
            buffered.append((geometry, 255))
    return rasterize(
        buffered,
        out_shape=(raster_size, raster_size),
        transform=transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )


def write_geojson(path, features, name):
    data = {
        "type": "FeatureCollection",
        "name": name,
        "features": [
            {
                "type": "Feature",
                "properties": feature["properties"],
                "geometry": mapping(feature["geometry"]),
            }
            for feature in features
        ],
    }
    write_json(path, data)


def road_mask(features, raster_size, transform):
    buffered = []
    for feature in features:
        highway = feature["properties"].get("highway") or "unclassified"
        width = ROAD_WIDTHS.get(highway, 4.0)
        geometry = clean_geometry(feature["geometry"].buffer(width / 2.0, cap_style="flat", join_style="round"))
        if geometry is not None:
            buffered.append((geometry, 255))
    return rasterize(
        buffered,
        out_shape=(raster_size, raster_size),
        transform=transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )


def landuse_masks(config, gpkg_path, to_working, to_world, land_projected, raster_size, transform):
    prepare(land_projected)
    categories = {"urban": [], "farmland": [], "forest": []}
    urban_values = {"residential", "commercial", "industrial", "retail"}
    farmland_values = {"farmland", "farmyard", "orchard", "meadow"}
    forest_values = {"forest"}
    for properties, geometry in iter_layer(gpkg_path, "polygons"):
        landuse = properties.get("landuse") or ""
        if landuse in urban_values:
            category = "urban"
        elif landuse in farmland_values:
            category = "farmland"
        elif landuse in forest_values:
            category = "forest"
        else:
            continue
        projected = clean_geometry(shapely_transform(to_working.transform, geometry))
        if projected is None or not projected.intersects(land_projected):
            continue
        categories[category].append((shapely_transform(to_world, projected), 255))

    output = {}
    for name, geometries in categories.items():
        output[name] = rasterize(
            geometries,
            out_shape=(raster_size, raster_size),
            transform=transform,
            fill=0,
            all_touched=True,
            dtype=np.uint8,
        )
    return output


def procedural_forest(land_mask, urban_mask, road_surface_mask, source_forest):
    raster_size = land_mask.shape[0]
    rng = np.random.default_rng(1837)
    coarse_size = max(32, raster_size // 48)
    coarse = (rng.random((coarse_size, coarse_size)) * 255).astype(np.uint8)
    noise = Image.fromarray(coarse, mode="L").resize((raster_size, raster_size), Image.Resampling.BILINEAR)
    noise = noise.filter(ImageFilter.GaussianBlur(radius=max(10, raster_size // 160)))
    generated = np.array(noise) > 126
    forest = generated | (source_forest > 0)
    forest &= land_mask > 0
    forest &= urban_mask == 0
    forest &= road_surface_mask == 0
    return forest.astype(np.uint8) * 255


def synthetic_wilderness_height(config, wilderness_mask, land_mask, pixel_size, land_floor):
    settings = config["surroundingWilderness"]["elevation"]
    raster_size = wilderness_mask.shape[0]
    rng = np.random.default_rng(int(settings["seed"]))

    def noise_layer(coarse_size, blur_radius):
        coarse = (rng.random((coarse_size, coarse_size)) * 255).astype(np.uint8)
        image = Image.fromarray(coarse, mode="L").resize((raster_size, raster_size), Image.Resampling.BICUBIC)
        image = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        return np.asarray(image, dtype=np.float32) / 255.0

    broad = noise_layer(max(18, raster_size // 128), max(30, raster_size // 55))
    medium = noise_layer(max(36, raster_size // 64), max(18, raster_size // 100))
    noise = broad * 0.72 + medium * 0.28
    low, high = np.percentile(noise[wilderness_mask > 0], [3.0, 97.0])
    noise = np.clip((noise - low) / max(high - low, 0.0001), 0.0, 1.0)
    noise = noise * noise * (3.0 - 2.0 * noise)

    minimum = float(settings["minimumInteriorMeters"])
    maximum = float(settings["maximumInteriorMeters"])
    target = minimum + noise * (maximum - minimum)

    coast_distance = distance_transform_edt(land_mask > 0) * pixel_size
    coast_alpha = np.clip(coast_distance / float(settings["coastlineRiseMeters"]), 0.0, 1.0)
    coast_alpha = coast_alpha * coast_alpha * (3.0 - 2.0 * coast_alpha)
    target = land_floor + coast_alpha * (target - land_floor)

    wilderness_distance = distance_transform_edt(wilderness_mask > 0) * pixel_size
    blend = np.clip(wilderness_distance / float(settings["transitionToMittenMeters"]), 0.0, 1.0)
    blend = blend * blend * (3.0 - 2.0 * blend)
    blend[wilderness_mask == 0] = 0.0
    return target.astype(np.float32), blend.astype(np.float32)


def reproject_dem(dem_paths, source_bounds, working_crs, raster_size):
    left, bottom, right, top = source_bounds
    pixel_size = (right - left) / raster_size
    if not math.isclose(pixel_size, (top - bottom) / raster_size, rel_tol=0.00001):
        raise RuntimeError("DEM source bounds must describe a square world transform.")
    transform = from_origin(left, top, pixel_size, pixel_size)
    destination = np.full((raster_size, raster_size), np.nan, dtype=np.float32)
    for path in dem_paths:
        with rasterio.open(path) as source:
            rasterio.warp.reproject(
                source=rasterio.band(source, 1),
                destination=destination,
                src_transform=source.transform,
                src_crs=source.crs,
                dst_transform=transform,
                dst_crs=working_crs,
                src_nodata=source.nodata,
                dst_nodata=np.nan,
                resampling=Resampling.bilinear,
                init_dest_nodata=False,
            )
    return destination


def save_mask(export_root, name, array, transform):
    masks_dir = export_root / "masks"
    masks_dir.mkdir(parents=True, exist_ok=True)
    png_path = masks_dir / f"{name}_mask_{array.shape[0]}.png"
    tif_path = masks_dir / f"{name}_mask_{array.shape[0]}.tif"
    Image.fromarray(array.astype(np.uint8), mode="L").save(png_path)
    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        width=array.shape[1],
        height=array.shape[0],
        count=1,
        dtype="uint8",
        transform=transform,
        nodata=0,
        compress="DEFLATE",
    ) as destination:
        destination.write(array.astype(np.uint8), 1)
    return {
        "path": str(png_path.relative_to(ROOT)).replace("\\", "/"),
        "geoTiff": str(tif_path.relative_to(ROOT)).replace("\\", "/"),
        "nonzeroPixels": int(np.count_nonzero(array)),
    }


def save_heightmap(export_root, prefix, height, transform, land_mask):
    height_dir = export_root / "heightmap"
    height_dir.mkdir(parents=True, exist_ok=True)
    tif_path = height_dir / f"{prefix}_float.tif"
    png_path = height_dir / f"{prefix}_height_{height.shape[0]}.png"
    preview_path = height_dir / f"{prefix}_height_preview.png"
    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        width=height.shape[1],
        height=height.shape[0],
        count=1,
        dtype="float32",
        transform=transform,
        compress="DEFLATE",
    ) as destination:
        destination.write(height.astype(np.float32), 1)

    valid = land_mask > 0
    min_height = float(np.min(height[valid]))
    max_height = float(np.max(height[valid]))
    normalized = np.zeros_like(height, dtype=np.uint16)
    if max_height > min_height:
        normalized[valid] = np.clip(
            (height[valid] - min_height) / (max_height - min_height) * 65535.0,
            0,
            65535,
        ).astype(np.uint16)
    Image.fromarray(normalized, mode="I;16").save(png_path)
    preview = (normalized.astype(np.float32) / 257.0).astype(np.uint8)
    Image.fromarray(preview, mode="L").save(preview_path)
    return {
        "floatTiff": str(tif_path.relative_to(ROOT)).replace("\\", "/"),
        "heightPng16": str(png_path.relative_to(ROOT)).replace("\\", "/"),
        "previewPng": str(preview_path.relative_to(ROOT)).replace("\\", "/"),
        "rasterSize": int(height.shape[0]),
        "pixelSizeMeters": float(transform.a),
        "elevationMeters": {
            "min": min_height,
            "max": max_height,
            "range": max_height - min_height,
        },
        "transform": [transform.a, transform.b, transform.c, transform.d, transform.e, transform.f],
    }


def world_point(longitude, latitude, to_working, to_world):
    projected_x, projected_y = to_working.transform(longitude, latitude)
    world_x, world_y = to_world(projected_x, projected_y)
    return float(world_x), float(world_y)


def make_names(config, to_working, to_world):
    names = []
    hometown = config["hometown"]
    home_x, home_y = world_point(
        hometown["center"]["longitude"],
        hometown["center"]["latitude"],
        to_working,
        to_world,
    )
    names.append(
        {
            "id": hometown["id"],
            "name": hometown["name"],
            "position": [round(home_x, 3), round(home_y, 3)],
            "type": hometown["mapType"],
            "radiusA": 900,
            "radiusB": 700,
            "angle": 0,
        }
    )
    for place in config["places"]:
        world_x, world_y = world_point(place["longitude"], place["latitude"], to_working, to_world)
        names.append(
            {
                "id": place["id"],
                "name": place["name"],
                "position": [round(world_x, 3), round(world_y, 3)],
                "type": place["type"],
                "radiusA": 420 if place["type"] == "NameCityCapital" else 300,
                "radiusB": 320 if place["type"] == "NameCityCapital" else 220,
                "angle": 0,
            }
        )
    return names, (home_x, home_y)


def main():
    parser = argparse.ArgumentParser(description="Build the compressed whole-Lower-Peninsula DayZ terrain sources.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--gpkg", default=str(DEFAULT_GPKG))
    parser.add_argument("--dem-metadata", default=str(DEFAULT_DEM_META))
    parser.add_argument("--dem-dir", default=str(DEFAULT_DEM_DIR))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT))
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--download-workers", type=int, default=4)
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    gpkg_path = Path(args.gpkg).resolve()
    dem_metadata = Path(args.dem_metadata).resolve()
    dem_dir = Path(args.dem_dir).resolve()
    export_root = Path(args.export_root).resolve()
    config = read_json(config_path)

    dem_paths = ensure_dem_files(dem_metadata, dem_dir, workers=args.download_workers)
    print(f"DEM tiles ready: {len(dem_paths)}", flush=True)
    if args.download_only:
        return

    world_size = float(config["worldSizeMeters"])
    raster_size = int(config["rasterSize"])
    game_pixel_size = world_size / raster_size
    working_crs = config["workingCrs"]
    to_working = Transformer.from_crs(config["sourceCrs"], working_crs, always_xy=True)

    mitten_projected, source_frame, great_lakes, state_boundary = build_land_geometry(config, gpkg_path, to_working)
    print("Lower Peninsula land component isolated.", flush=True)
    mapping_info = build_world_mapping(config, mitten_projected)
    to_world = world_transformer(mapping_info)
    minx, miny, _, _ = mapping_info["sourceLandBounds"]
    scale = mapping_info["scale"]
    source_left = minx - mapping_info["offsetX"] / scale
    source_bottom = miny - mapping_info["offsetY"] / scale
    source_span = world_size / scale
    source_bounds = (source_left, source_bottom, source_left + source_span, source_bottom + source_span)
    regional_frame = box(*source_bounds)
    regional_land_projected = clean_geometry(regional_frame.difference(great_lakes))
    land_world = clean_geometry(shapely_transform(to_world, regional_land_projected))
    mitten_world = clean_geometry(shapely_transform(to_world, mitten_projected))
    game_transform = from_origin(0.0, world_size, game_pixel_size, game_pixel_size)
    land_mask = rasterize(
        [(land_world, 255)],
        out_shape=(raster_size, raster_size),
        transform=game_transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )
    mitten_mask = rasterize(
        [(mitten_world, 255)],
        out_shape=(raster_size, raster_size),
        transform=game_transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )
    navigation_features = build_navigation_waterways(config, gpkg_path, to_working, to_world)
    navigation_mask = navigation_water_mask(config, navigation_features, raster_size, game_transform)
    land_mask[navigation_mask > 0] = 0
    mitten_mask[navigation_mask > 0] = 0
    wilderness_mask = np.where((land_mask > 0) & (mitten_mask == 0), 255, 0).astype(np.uint8)
    water_mask = np.where(land_mask > 0, 0, 255).astype(np.uint8)
    print(f"World fit calculated at 1:{mapping_info['realMetersPerGameMeter']:.2f}.", flush=True)

    major_roads, hometown_roads = build_road_features(
        config,
        gpkg_path,
        to_working,
        to_world,
        mitten_projected,
    )
    all_roads = major_roads + hometown_roads
    print(f"Road vectors transformed: {len(major_roads)} statewide, {len(hometown_roads)} Hometown.", flush=True)
    roads_surface = road_mask(all_roads, raster_size, game_transform)
    roads_surface[mitten_mask == 0] = 0
    landuse = landuse_masks(
        config,
        gpkg_path,
        to_working,
        to_world,
        mitten_projected,
        raster_size,
        game_transform,
    )
    for landuse_mask in landuse.values():
        landuse_mask[mitten_mask == 0] = 0
    forest_mask = procedural_forest(land_mask, landuse["urban"], roads_surface, landuse["forest"])
    forest_mask[wilderness_mask > 0] = 255
    print("Surface masks generated.", flush=True)

    dem = reproject_dem(dem_paths, source_bounds, working_crs, raster_size)
    print("Elevation tiles reprojected into game coordinates.", flush=True)
    valid_land = (land_mask > 0) & np.isfinite(dem)
    if not np.any(valid_land):
        raise RuntimeError("The statewide DEM did not overlap the Lower Peninsula land mask.")
    fallback = float(np.nanmedian(dem[valid_land]))
    dem = np.where(np.isfinite(dem), dem, fallback)
    elevation = config["elevation"]
    height = (dem - float(elevation["greatLakesDatumMeters"])) * float(elevation["verticalScale"])
    height += float(elevation["landFloorMeters"])
    height = np.maximum(height, float(elevation["landFloorMeters"]))
    wilderness_target, wilderness_blend = synthetic_wilderness_height(
        config,
        wilderness_mask,
        land_mask,
        game_pixel_size,
        float(elevation["landFloorMeters"]),
    )
    height = height * (1.0 - wilderness_blend) + wilderness_target * wilderness_blend
    road_pixels = (roads_surface > 0) & (land_mask > 0)
    height[road_pixels] = np.maximum(height[road_pixels], float(elevation["roadFloorMeters"]))
    height[land_mask == 0] = float(elevation["waterDepthMeters"])

    height_meta = save_heightmap(export_root, config["outputPrefix"], height, game_transform, land_mask)
    masks = {
        "water": save_mask(export_root, "water", water_mask, game_transform),
        "woods": save_mask(export_root, "woods", forest_mask, game_transform),
        "roads": save_mask(export_root, "roads", roads_surface, game_transform),
        "farmland": save_mask(export_root, "farmland", landuse["farmland"], game_transform),
        "urban": save_mask(export_root, "urban", landuse["urban"], game_transform),
        "mitten": save_mask(export_root, "mitten", mitten_mask, game_transform),
        "wilderness": save_mask(export_root, "wilderness", wilderness_mask, game_transform),
        "navigation": save_mask(export_root, "navigation", navigation_mask, game_transform),
    }

    vector_dir = export_root / "vectors"
    (vector_dir / "lower_peninsula_land_world.geojson").unlink(missing_ok=True)
    write_geojson(vector_dir / "major_roads_world.geojson", major_roads, "major_roads_world")
    write_geojson(vector_dir / "hometown_roads_world.geojson", hometown_roads, "hometown_roads_world")
    write_geojson(vector_dir / "navigation_waterways_world.geojson", navigation_features, "navigation_waterways_world")
    write_geojson(
        vector_dir / "regional_land_world.geojson",
        [{"properties": {"name": "Regional land and wilderness"}, "geometry": land_world}],
        "regional_land_world",
    )
    write_geojson(
        vector_dir / "mitten_mainland_world.geojson",
        [{"properties": {"name": "Michigan Lower Peninsula"}, "geometry": mitten_world}],
        "mitten_mainland_world",
    )

    names, hometown_center = make_names(config, to_working, to_world)
    hometown_spawns = [
        [round(hometown_center[0] + offset[0], 3), round(hometown_center[1] + offset[1], 3)]
        for offset in config["hometown"]["spawnOffsetsMeters"]
    ]
    metadata = {
        "terrainName": config["terrainName"],
        "prototypeName": config["prototypeName"],
        "outputPrefix": config["outputPrefix"],
        "crs": "LOCAL_GAME_METERS",
        "sourceCrs": working_crs,
        "sizeMeters": world_size,
        "centerWgs84": {"name": "Lower Peninsula", "latitude": 43.76, "longitude": -84.65},
        "centerProjected": {"easting": world_size / 2.0, "northing": world_size / 2.0},
        "centerUtm16n": {"easting": world_size / 2.0, "northing": world_size / 2.0},
        "boundsProjected": {"west": 0.0, "south": 0.0, "east": world_size, "north": world_size},
        "boundsUtm16n": {"west": 0.0, "south": 0.0, "east": world_size, "north": world_size},
        "sourceBoundsProjected": {
            "west": source_bounds[0],
            "south": source_bounds[1],
            "east": source_bounds[2],
            "north": source_bounds[3],
        },
        "worldMapping": mapping_info,
        "heightmap": height_meta,
        "masks": masks,
        "names": names,
        "hometown": {
            "name": config["hometown"]["name"],
            "center": [round(hometown_center[0], 3), round(hometown_center[1], 3)],
            "primarySpawnArea": True,
            "spawnPositions": hometown_spawns,
            "sourceBoundsWgs84": config["hometown"]["boundsWgs84"],
        },
        "surroundingWilderness": {
            **config["surroundingWilderness"],
            "mask": masks["wilderness"]["path"],
        },
        "vectorLayerFeatureCounts": {
            "roads": len(major_roads),
            "hometown_roads": len(hometown_roads),
            "waterways": len(navigation_features),
            "water_polygons": len(polygon_parts(great_lakes)),
            "woods": int(np.count_nonzero(forest_mask)),
            "landuse": int(np.count_nonzero(landuse["urban"]) + np.count_nonzero(landuse["farmland"])),
        },
        "sourceFiles": {
            "bounds": str(config_path.relative_to(ROOT)).replace("\\", "/"),
            "osm": str(gpkg_path.relative_to(ROOT)).replace("\\", "/"),
            "demMetadata": str(dem_metadata.relative_to(ROOT)).replace("\\", "/"),
            "dems": [str(path.relative_to(ROOT)).replace("\\", "/") for path in dem_paths],
        },
    }
    write_json(export_root / "terrain_builder_export_metadata.json", metadata)

    preview_dir = ROOT / "build" / "diagnostics"
    preview_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(export_root / "heightmap" / f"{config['outputPrefix']}_height_preview.png", preview_dir / "michigan-lower-peninsula-height.png")
    Image.fromarray(land_mask, mode="L").save(preview_dir / "michigan-lower-peninsula-land-mask.png")
    Image.fromarray(roads_surface, mode="L").save(preview_dir / "michigan-lower-peninsula-road-mask.png")

    print(f"Whole-mitten export complete: {export_root}")
    print(f"Scale: 1:{mapping_info['realMetersPerGameMeter']:.2f}")
    print(f"Major road features: {len(major_roads)}")
    print(f"Hometown road features: {len(hometown_roads)}")
    print(f"Hometown center: {hometown_center[0]:.1f}, {hometown_center[1]:.1f}")


if __name__ == "__main__":
    main()
