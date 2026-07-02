import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
EXPORT_ROOT = ROOT / "terrain" / "exports" / "utm16n"
META_FILE = EXPORT_ROOT / "terrain_builder_export_metadata.json"
PACKAGE_ROOT = ROOT / "terrain" / "terrain-builder" / "MichiganSurvival"
SOURCE_DIR = PACKAGE_ROOT / "source"

SURFACES = {
    "grass": (80, 170, 70),
    "forest": (25, 95, 45),
    "water": (35, 95, 170),
    "road": (125, 120, 110),
    "farmland": (185, 160, 75),
    "urban": (150, 80, 80),
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_mask(name):
    path = EXPORT_ROOT / "masks" / f"{name}_mask_4096.png"
    return np.array(Image.open(path).convert("L")) > 0


def write_asc(meta):
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    out = SOURCE_DIR / "michigan_survival_height_4096.asc"
    float_tif = ROOT / meta["heightmap"]["floatTiff"]
    with rasterio.open(float_tif) as src:
        arr = src.read(1)
        transform = src.transform
        nodata = -9999
        arr = np.where(np.isfinite(arr), arr, nodata)

    nrows, ncols = arr.shape
    xll = transform.c
    yll = transform.f + transform.e * nrows
    cell = transform.a

    with out.open("w", encoding="ascii", newline="\n") as f:
        f.write(f"ncols {ncols}\n")
        f.write(f"nrows {nrows}\n")
        f.write(f"xllcorner {xll:.6f}\n")
        f.write(f"yllcorner {yll:.6f}\n")
        f.write(f"cellsize {cell:.8f}\n")
        f.write(f"NODATA_value {nodata}\n")
        for row in arr:
            f.write(" ".join(f"{value:.3f}" for value in row))
            f.write("\n")
    return out


def create_mask_satellite_and_legend():
    height_preview = np.array(Image.open(EXPORT_ROOT / "heightmap" / "michigan_survival_traverse_10km_utm16n_height_preview.png").convert("L"))
    masks = {
        "water": load_mask("water"),
        "roads": load_mask("roads"),
        "woods": load_mask("woods"),
        "farmland": load_mask("farmland"),
        "urban": load_mask("urban"),
    }

    size = height_preview.shape
    mask_rgb = np.zeros((size[0], size[1], 3), dtype=np.uint8)
    mask_rgb[:, :] = SURFACES["grass"]
    mask_rgb[masks["farmland"]] = SURFACES["farmland"]
    mask_rgb[masks["woods"]] = SURFACES["forest"]
    mask_rgb[masks["urban"]] = SURFACES["urban"]
    mask_rgb[masks["roads"]] = SURFACES["road"]
    mask_rgb[masks["water"]] = SURFACES["water"]

    mask_path = SOURCE_DIR / "michigan_survival_mask_lco.png"
    Image.fromarray(mask_rgb, mode="RGB").save(mask_path)

    shade = height_preview.astype(np.float32) / 255.0
    sat = mask_rgb.astype(np.float32) * (0.62 + shade[:, :, None] * 0.45)
    sat = np.clip(sat, 0, 255).astype(np.uint8)
    sat_path = SOURCE_DIR / "michigan_survival_sat_lco.png"
    Image.fromarray(sat, mode="RGB").filter(ImageFilter.GaussianBlur(radius=0.35)).save(sat_path)

    legend = Image.new("RGB", (6, 1))
    for idx, name in enumerate(["grass", "forest", "water", "road", "farmland", "urban"]):
        legend.putpixel((idx, 0), SURFACES[name])
    legend_path = SOURCE_DIR / "mapLegend.png"
    legend.save(legend_path)

    return mask_path, sat_path, legend_path


def write_layers_cfg():
    out = SOURCE_DIR / "layers.cfg"
    out.write_text(
        """class Layers
{
    class michigan_grass
    {
        texture = "";
        material = "MichiganSurvival\\data\\michigan_grass.rvmat";
    };
    class michigan_forest
    {
        texture = "";
        material = "MichiganSurvival\\data\\michigan_forest.rvmat";
    };
    class michigan_water
    {
        texture = "";
        material = "MichiganSurvival\\data\\michigan_water.rvmat";
    };
    class michigan_road
    {
        texture = "";
        material = "MichiganSurvival\\data\\michigan_road.rvmat";
    };
    class michigan_farmland
    {
        texture = "";
        material = "MichiganSurvival\\data\\michigan_farmland.rvmat";
    };
    class michigan_urban
    {
        texture = "";
        material = "MichiganSurvival\\data\\michigan_urban.rvmat";
    };
};

class Legend
{
    picture = "MichiganSurvival\\source\\mapLegend.png";
    class Colors
    {
        michigan_grass[] = {80, 170, 70};
        michigan_forest[] = {25, 95, 45};
        michigan_water[] = {35, 95, 170};
        michigan_road[] = {125, 120, 110};
        michigan_farmland[] = {185, 160, 75};
        michigan_urban[] = {150, 80, 80};
    };
};
""",
        encoding="ascii",
    )
    return out


def write_config():
    out = PACKAGE_ROOT / "config.cpp"
    out.write_text(
        """#define ReadOnlyVerified 3

class CfgPatches
{
    class MichiganSurvival
    {
        units[] = {"MichiganSurvival"};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data", "DZ_Surfaces_Bliss"};
    };
};

class CfgWorlds
{
    class DefaultWorld;
    class CAWorld: DefaultWorld {};

    class MichiganSurvival: CAWorld
    {
        access = ReadOnlyVerified;
        description = "Michigan Survival";
        worldName = "MichiganSurvival\\world\\MichiganSurvival.wrp";
        mapSize = 10000;
        cutscenes[] = {};
        startTime = "12:00";
        startDate = "06/01/2026";
        startWeather = 0.35;
        startFog = 0.05;
        forecastWeather = 0.35;
        forecastFog = 0.05;
        centerPosition[] = {5000, 5000, 80};
        seagullPos[] = {5000, 5000, 120};
        longitude = -85;
        latitude = 44;
        clutterGrid = 1.0;
        clutterDist = 125;
        noDetailDist = 65;
        fullDetailDist = 15;
        midDetailTexture = "DZ\\surfaces_bliss\\data\\terrain\\cp_grass_ca.paa";

        class Names
        {
            class TraverseCity
            {
                name = "Traverse City";
                position[] = {5000, 5000};
                type = "NameCityCapital";
                radiusA = 650;
                radiusB = 650;
                angle = 0;
            };
            class DowntownTraverseCity
            {
                name = "Downtown Traverse City";
                position[] = {4666, 5083};
                type = "NameCity";
                radiusA = 300;
                radiusB = 300;
                angle = 0;
            };
            class GrandTraverseBay
            {
                name = "Grand Traverse Bay";
                position[] = {8132, 9710};
                type = "NameMarine";
                radiusA = 1000;
                radiusB = 750;
                angle = 0;
            };
            class WestGrandTraverseBay
            {
                name = "West Grand Traverse Bay";
                position[] = {2620, 8171};
                type = "NameMarine";
                radiusA = 900;
                radiusB = 650;
                angle = 0;
            };
            class EastGrandTraverseBay
            {
                name = "East Grand Traverse Bay";
                position[] = {9000, 7600};
                type = "NameMarine";
                radiusA = 900;
                radiusB = 650;
                angle = 0;
            };
            class BoardmanLake
            {
                name = "Boardman Lake";
                position[] = {5862, 2759};
                type = "NameMarine";
                radiusA = 360;
                radiusB = 520;
                angle = 0;
            };
            class BoardmanRiver
            {
                name = "Boardman River";
                position[] = {4552, 3870};
                type = "NameLocal";
                radiusA = 300;
                radiusB = 300;
                angle = 0;
            };
            class CherryCapitalAirport
            {
                name = "Cherry Capital Airport";
                position[] = {8081, 2653};
                type = "NameLocal";
                radiusA = 500;
                radiusB = 350;
                angle = 0;
            };
            class GarfieldTownship
            {
                name = "Garfield Township";
                position[] = {1886, 4715};
                type = "NameVillage";
                radiusA = 500;
                radiusB = 400;
                angle = 0;
            };
        };
    };

    initWorld = "MichiganSurvival";
    demoWorld = "MichiganSurvival";
};

class CfgWorldList
{
    class MichiganSurvival {};
};
""",
        encoding="ascii",
    )
    return out


def write_readme(meta, asc_path, mask_path, sat_path, legend_path, layers_path, config_path):
    out = PACKAGE_ROOT / "README.md"
    out.write_text(
        f"""# MichiganSurvival Terrain Builder Package

Fresh 10 km x 10 km Traverse City prototype.

## Terrain Builder Values

- Terrain name: `MichiganSurvival`
- Terrain size: `{meta["sizeMeters"]} x {meta["sizeMeters"]}` meters
- Heightmap resolution: `{meta["heightmap"]["rasterSize"]} x {meta["heightmap"]["rasterSize"]}`
- Cell size: `{meta["heightmap"]["pixelSizeMeters"]}` meters
- UTM zone: `16`
- UTM subzone: `T`
- Left-bottom easting: `{meta["boundsUtm16n"]["west"]:.6f}`
- Left-bottom northing: `{meta["boundsUtm16n"]["south"]:.6f}`

## Import Files

- Heightmap ASC: `{asc_path.relative_to(PACKAGE_ROOT)}`
- Satellite image: `{sat_path.relative_to(PACKAGE_ROOT)}`
- Surface mask: `{mask_path.relative_to(PACKAGE_ROOT)}`
- Map legend: `{legend_path.relative_to(PACKAGE_ROOT)}`
- Layers config: `{layers_path.relative_to(PACKAGE_ROOT)}`
- Config: `{config_path.relative_to(PACKAGE_ROOT)}`

Save Terrain Builder project immediately as:

`P:\\MichiganSurvival\\MichiganSurvival.pew`
""",
        encoding="ascii",
    )
    return out


def main():
    meta = read_json(META_FILE)
    for folder in ["data", "world", "source", "ce", "navmesh"]:
        (PACKAGE_ROOT / folder).mkdir(parents=True, exist_ok=True)
    asc = write_asc(meta)
    mask, sat, legend = create_mask_satellite_and_legend()
    layers = write_layers_cfg()
    config = write_config()
    write_readme(meta, asc, mask, sat, legend, layers, config)
    print(f"Wrote Terrain Builder package to {PACKAGE_ROOT}")
    print(f"Height ASC: {asc}")
    print(f"Satellite: {sat}")
    print(f"Mask: {mask}")


if __name__ == "__main__":
    main()
