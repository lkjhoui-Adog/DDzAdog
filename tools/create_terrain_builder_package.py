import argparse
import json
import re
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

DAYZ_WORLD_WEATHER_BLOCK = r"""
		class Weather
		{
			class Overcast
			{
				class Weather1
				{
					overcast=0.07;
					lightingOvercast=0;
					sky="#(argb,8,8,3)color(0.560784,0.572549,0.623529,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=1;
					godrayStrength=0.050000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather2
				{
					overcast=0.1;
					lightingOvercast=0.15000001;
					sky="#(argb,8,8,3)color(0.560784,0.572549,0.623529,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage10_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=1;
					godrayStrength=0.050000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather3
				{
					overcast=0.16;
					lightingOvercast=0.15000001;
					sky="#(argb,8,8,3)color(0.560784,0.572549,0.623529,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage11_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=1;
					godrayStrength=0.050000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather4
				{
					overcast=0.22;
					lightingOvercast=0.15000001;
					sky="#(argb,8,8,3)color(0.560784,0.572549,0.623529,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage12_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=1;
					godrayStrength=0.050000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather5
				{
					overcast=0.28;
					lightingOvercast=0.15000001;
					sky="#(argb,8,8,3)color(0.560784,0.572549,0.623529,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage13_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=1;
					godrayStrength=0.050000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather6
				{
					overcast=0.34;
					lightingOvercast=0.15000001;
					sky="#(argb,8,8,3)color(0.560784,0.572549,0.623529,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage14_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=1;
					godrayStrength=0.050000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather7
				{
					overcast=0.40000001;
					lightingOvercast=0.15000001;
					sky="#(argb,8,8,3)color(0.45098,0.490196,0.611765,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\enoch\data\Sky_Stage10_Cirrus_en_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage15_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=0.80000001;
					godrayStrength=0.15000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather8
				{
					overcast=0.46000001;
					lightingOvercast=0.15000001;
					sky="#(argb,8,8,3)color(0.45098,0.490196,0.611765,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\enoch\data\Sky_Stage10_Cirrus_en_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage16_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=0.64999998;
					godrayStrength=0.15000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather9
				{
					overcast=0.51999998;
					lightingOvercast=0.30000001;
					sky="#(argb,8,8,3)color(0.45098,0.490196,0.611765,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\enoch\data\Sky_Stage10_Cirrus_en_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage16_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=0.60000002;
					godrayStrength=0.1;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather10
				{
					overcast=0.57999998;
					lightingOvercast=0.57999998;
					sky="#(argb,8,8,3)color(0.45098,0.490196,0.611765,1.0,CO)";
					farCloud="DZ\worlds\chernarusplus\data\Cloud_Stage20_Altostratus_sky.paa";
					skyR="DZ\data\data\sky_semicloudy_lco.paa";
					cloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloudClip=0;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage02_FoggyHills_sky.paa";
					horizonClip=0;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=0.40000001;
					godrayStrength=0;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather11
				{
					overcast=0.77999997;
					lightingOvercast=1;
					sky="#(argb,8,8,3)color(0.141176,0.168627,0.215686,1.0,CO)";
					skyR="DZ\data\data\sky_mostlycloudy_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Sky_Stage30_Stratocumulus_sky.paa";
					cloud="DZ\worlds\chernarusplus\data\Cloud_Stage30_Nimbostratus_sky.paa";
					cloudClip=0;
					horizon="DZ\worlds\chernarusplus\data\Cloud_Stage00_Transparent_sky.paa";
					horizonClip=0;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=0;
					godrayStrength=0;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather12
				{
					overcast=1.01;
					lightingOvercast=1;
					sky="#(argb,8,8,3)color(0.141176,0.141176,0.141176,1.0,CO)";
					skyR="DZ\data\data\sky_mostlycloudy_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Sky_Stage30_Stratocumulus_sky.paa";
					cloud="DZ\worlds\chernarusplus\data\Cloud_Stage31_Nimbostratus_sky.paa";
					cloudClip=0;
					horizon="DZ\worlds\chernarusplus\data\Cloud_Stage00_Transparent_sky.paa";
					horizonClip=0;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=0;
					godrayStrength=0;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
			};
			class VolFog
			{
				CameraFog=0;
				Item1[]={500,0.059999999,0.93000001,0.13,1};
				Item2[]={1100,0.5,0.2,0.1,1};
				Item3[]={1300,0.0099999998,0.89999998,0.050000001,1};
				UseDynamic=1;
			};
		};
		volFogOffset=170;
		spaceObject="DZ\Data\data\milkyway.p3d";
		spaceObjectRotationPreOffset[]={0,0,0};
		spaceObjectRotationOffset[]={0,0,0};
		spaceTexture0="DZ\Data\data\milkyway_left_co.paa";
		spaceTexture1="DZ\Data\data\milkyway_right_co.paa";
		atmosphereObject="DZ\Data\data\atmosphere.p3d";
		atmosphereTexture="DZ\worlds\chernarusplus\data\Sky_Stage01_Clear_sky.paa";
		farCloudObject="DZ\Data\data\obloha.p3d";
		farCloudObjectRotationAxis[]={0,1,0};
		farCloudObjectRotationSpeed=3;
		cloudObject="DZ\Data\data\cloudObject.p3d";
		cloudObjectRotationAxis[]={0,1,0};
		cloudObjectRotationSpeed=9;
		horizonObject="DZ\Data\data\horizont.p3d";
		horizonObjectRotationAxis[]={0,1,0};
		horizonObjectRotationSpeed=0;
"""
def project_path(value):
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def class_name(value):
    safe = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not safe or safe[0].isdigit():
        safe = f"Name_{safe}"
    return safe


def rel(path, base):
    try:
        return path.relative_to(base)
    except ValueError:
        return path


def load_mask(meta, name):
    path = ROOT / meta["masks"][name]["path"]
    return np.array(Image.open(path).convert("L")) > 0


def write_asc(meta):
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    out = SOURCE_DIR / f"{meta['outputPrefix']}_height_{meta['heightmap']['rasterSize']}.asc"
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


def create_mask_satellite_and_legend(meta):
    height_preview = np.array(Image.open(ROOT / meta["heightmap"]["previewPng"]).convert("L"))
    masks = {
        "water": load_mask(meta, "water"),
        "roads": load_mask(meta, "roads"),
        "woods": load_mask(meta, "woods"),
        "farmland": load_mask(meta, "farmland"),
        "urban": load_mask(meta, "urban"),
    }

    size = height_preview.shape
    mask_rgb = np.zeros((size[0], size[1], 3), dtype=np.uint8)
    mask_rgb[:, :] = SURFACES["grass"]
    mask_rgb[masks["farmland"]] = SURFACES["farmland"]
    mask_rgb[masks["woods"]] = SURFACES["forest"]
    mask_rgb[masks["urban"]] = SURFACES["urban"]
    mask_rgb[masks["roads"]] = SURFACES["road"]
    mask_rgb[masks["water"]] = SURFACES["water"]

    mask_path = SOURCE_DIR / f"{meta['outputPrefix']}_mask_lco.png"
    Image.fromarray(mask_rgb, mode="RGB").save(mask_path)

    shade = height_preview.astype(np.float32) / 255.0
    sat = mask_rgb.astype(np.float32) * (0.62 + shade[:, :, None] * 0.45)
    sat = np.clip(sat, 0, 255).astype(np.uint8)
    sat_path = SOURCE_DIR / f"{meta['outputPrefix']}_sat_lco.png"
    Image.fromarray(sat, mode="RGB").filter(ImageFilter.GaussianBlur(radius=0.35)).save(sat_path)

    legend = Image.new("RGB", (6, 1))
    for idx, name in enumerate(["grass", "forest", "water", "road", "farmland", "urban"]):
        legend.putpixel((idx, 0), SURFACES[name])
    legend_path = SOURCE_DIR / "mapLegend.png"
    legend.save(legend_path)

    return mask_path, sat_path, legend_path


def write_layers_cfg(meta):
    terrain_name = meta["terrainName"]
    out = SOURCE_DIR / "layers.cfg"
    out.write_text(
        f"""class Layers
{{
    class michigan_grass
    {{
        texture = "";
        material = "{terrain_name}\\data\\michigan_grass.rvmat";
    }};
    class michigan_forest
    {{
        texture = "";
        material = "{terrain_name}\\data\\michigan_forest.rvmat";
    }};
    class michigan_water
    {{
        texture = "";
        material = "{terrain_name}\\data\\michigan_water.rvmat";
    }};
    class michigan_road
    {{
        texture = "";
        material = "{terrain_name}\\data\\michigan_road.rvmat";
    }};
    class michigan_farmland
    {{
        texture = "";
        material = "{terrain_name}\\data\\michigan_farmland.rvmat";
    }};
    class michigan_urban
    {{
        texture = "";
        material = "{terrain_name}\\data\\michigan_urban.rvmat";
    }};
}};

class Legend
{{
    picture = "{terrain_name}\\source\\mapLegend.png";
    class Colors
    {{
        michigan_grass[] = {{80, 170, 70}};
        michigan_forest[] = {{25, 95, 45}};
        michigan_water[] = {{35, 95, 170}};
        michigan_road[] = {{125, 120, 110}};
        michigan_farmland[] = {{185, 160, 75}};
        michigan_urban[] = {{150, 80, 80}};
    }};
}};
""",
        encoding="ascii",
    )
    return out


def names_block(meta):
    names = meta.get("names") or [
        {
            "id": meta["terrainName"],
            "name": meta["centerWgs84"].get("name", meta["terrainName"]),
            "position": [meta["sizeMeters"] / 2, meta["sizeMeters"] / 2],
            "type": "NameCityCapital",
            "radiusA": 650,
            "radiusB": 650,
            "angle": 0,
        }
    ]
    lines = ["        class Names", "        {"]
    for item in names:
        pos = item.get("position", [meta["sizeMeters"] / 2, meta["sizeMeters"] / 2])
        lines.extend(
            [
                f"            class {class_name(item.get('id', item.get('name', 'Name')))}",
                "            {",
                f"                name = \"{item.get('name', 'Unnamed')}\";",
                f"                position[] = {{{float(pos[0]):.3f}, {float(pos[1]):.3f}}};",
                f"                type = \"{item.get('type', 'NameVillage')}\";",
                f"                radiusA = {float(item.get('radiusA', 500)):.3f};",
                f"                radiusB = {float(item.get('radiusB', 500)):.3f};",
                f"                angle = {float(item.get('angle', 0)):.3f};",
                "            };",
            ]
        )
    lines.append("        };")
    return "\n".join(lines)


def write_config(meta):
    terrain_name = meta["terrainName"]
    center = meta["sizeMeters"] / 2
    longitude = float(meta["centerWgs84"]["longitude"])
    latitude = float(meta["centerWgs84"]["latitude"])
    out = PACKAGE_ROOT / "config.cpp"
    out.write_text(
        f"""#define ReadOnlyVerified 3

class CfgPatches
{{
    class {terrain_name}
    {{
        units[] = {{"{terrain_name}"}};
        weapons[] = {{}};
        requiredVersion = 0.1;
        requiredAddons[] = {{"DZ_Data", "DZ_Surfaces_Bliss", "DZ_Worlds_Chernarusplus_World", "DZ_Worlds_Enoch"}};
    }};
}};

class CfgWorlds
{{
    class DefaultWorld;
    class CAWorld;

    class {terrain_name}: CAWorld
    {{
        access = ReadOnlyVerified;
        description = "{meta['prototypeName']}";
        worldName = "{terrain_name}\\world\\{terrain_name}.wrp";
        ceFiles = "DZ\\worlds\\chernarusplus\\ce";
        class Navmesh
        {{
            navmeshName = "\\{terrain_name}\\navmesh\\navmesh.nm";
            filterIsolatedIslandsOnLoad = 1;
            visualiseOffset = 0;
            class GenParams
            {{
                tileWidth = 50;
                cellSize1 = 0.25;
                cellSize2 = 0.1;
                cellSize3 = 0.1;
                filterIsolatedIslands = 1;
                seedPosition[] = {{7500, 0, 7500}};
                class Agent
                {{
                    diameter = 0.60000002;
                    standHeight = 1.5;
                    crouchHeight = 1;
                    proneHeight = 0.5;
                    maxStepHeight = 0.44999999;
                    maxSlope = 60;
                }};
                class Links
                {{
                    class ZedJump387_050
                    {{
                        jumpLength = 1.5;
                        jumpHeight = 0.5;
                        minCenterHeight = 0.30000001;
                        jumpDropdownMin = 0.5;
                        jumpDropdownMax = -0.5;
                        areaType = "jump0";
                        flags[] = {{"jumpOver"}};
                        color = 1727987712;
                    }};
                    class ZedJump388_050
                    {{
                        jumpLength = 1.5;
                        jumpHeight = 0.5;
                        minCenterHeight = -0.5;
                        jumpDropdownMin = 0.5;
                        jumpDropdownMax = -0.5;
                        areaType = "jump0";
                        flags[] = {{"jumpOver"}};
                        color = 1725781248;
                    }};
                    class ZedJump387_110
                    {{
                        jumpLength = 3.9000001;
                        jumpHeight = 1.1;
                        minCenterHeight = 0.5;
                        jumpDropdownMin = 0.5;
                        jumpDropdownMax = -0.5;
                        areaType = "jump0";
                        flags[] = {{"jumpOver"}};
                        color = 1711308800;
                    }};
                    class ZedJump420_160
                    {{
                        jumpLength = 4;
                        jumpHeight = 1.6;
                        minCenterHeight = 1.1;
                        jumpDropdownMin = 0.5;
                        jumpDropdownMax = -0.5;
                        areaType = "jump0";
                        flags[] = {{"jumpOver"}};
                        color = 1711276287;
                    }};
                    class ZedJump265_210
                    {{
                        jumpLength = 2.45;
                        jumpHeight = 2.5;
                        minCenterHeight = 1.8;
                        jumpDropdownMin = 0.5;
                        jumpDropdownMax = -0.5;
                        areaType = "jump0";
                        flags[] = {{"climb"}};
                        color = 1720975571;
                    }};
                    class Fence50_110deer
                    {{
                        typeId = 100;
                        jumpLength = 8;
                        jumpHeight = 1.1;
                        minCenterHeight = 0.5;
                        jumpDropdownMin = 1;
                        jumpDropdownMax = -1;
                        areaType = "jump2";
                        flags[] = {{"jumpOver"}};
                        color = 1722460927;
                    }};
                    class Fence110_160deer
                    {{
                        typeId = 101;
                        jumpLength = 8;
                        jumpHeight = 1.6;
                        minCenterHeight = 1.1;
                        jumpDropdownMin = 1;
                        jumpDropdownMax = -1;
                        areaType = "jump3";
                        flags[] = {{"jumpOver"}};
                        color = 1713700856;
                    }};
                    class Fence50_110hen
                    {{
                        typeId = 110;
                        jumpLength = 4;
                        jumpHeight = 1.1;
                        minCenterHeight = 0.5;
                        jumpDropdownMin = 0.5;
                        jumpDropdownMax = -0.5;
                        areaType = "jump4";
                        flags[] = {{"jumpOver"}};
                        color = -22016;
                    }};
                    class Fence110_160hen
                    {{
                        typeId = 111;
                        jumpLength = 4;
                        jumpHeight = 1.6;
                        minCenterHeight = 1.1;
                        jumpDropdownMin = 0.5;
                        jumpDropdownMax = -0.5;
                        areaType = "jump4";
                        flags[] = {{"jumpOver"}};
                        color = -22016;
                    }};
                }};
            }};
        }};
        mapSize = {int(meta['sizeMeters'])};
        cutscenes[] = {{}};
        startTime = "12:00";
        startDate = "06/01/2026";
        startWeather = 0.35;
        startFog = 0.05;
        forecastWeather = 0.35;
        forecastFog = 0.05;
        centerPosition[] = {{{center:.3f}, {center:.3f}, 80}};
        seagullPos[] = {{{center:.3f}, {center:.3f}, 120}};
        longitude = {longitude:.6f};
        latitude = {latitude:.6f};
        clutterGrid = 1.0;
        clutterDist = 125;
        noDetailDist = 65;
        fullDetailDist = 15;
        midDetailTexture = "DZ\\surfaces_bliss\\data\\terrain\\cp_grass_ca.paa";
        heightBlendingMode = 1;
        bicubicMode = 1;

{DAYZ_WORLD_WEATHER_BLOCK}

        class UsedTerrainMaterials
        {{
            material0 = "{terrain_name}\\data\\michigan_grass.rvmat";
            material1 = "{terrain_name}\\data\\michigan_forest.rvmat";
            material2 = "{terrain_name}\\data\\michigan_water.rvmat";
            material3 = "{terrain_name}\\data\\michigan_road.rvmat";
            material4 = "{terrain_name}\\data\\michigan_farmland.rvmat";
            material5 = "{terrain_name}\\data\\michigan_urban.rvmat";
        }};

{names_block(meta)}
    }};

    initWorld = "{terrain_name}";
    demoWorld = "{terrain_name}";
}};

class CfgWorldList
{{
    class {terrain_name} {{}};
}};
""",
        encoding="ascii",
    )
    return out


def write_readme(meta, asc_path, mask_path, sat_path, legend_path, layers_path, config_path):
    out = PACKAGE_ROOT / "README.md"
    out.write_text(
        f"""# {meta['terrainName']} Terrain Builder Package

{meta['prototypeName']}.

## Terrain Builder Values

- Terrain name: `{meta['terrainName']}`
- Terrain size: `{meta['sizeMeters']} x {meta['sizeMeters']}` meters
- Heightmap resolution: `{meta['heightmap']['rasterSize']} x {meta['heightmap']['rasterSize']}`
- Cell size: `{meta['heightmap']['pixelSizeMeters']}` meters
- CRS: `{meta['crs']}`
- Left-bottom easting: `{meta['boundsProjected']['west']:.6f}`
- Left-bottom northing: `{meta['boundsProjected']['south']:.6f}`

## Import Files

- Heightmap ASC: `{rel(asc_path, PACKAGE_ROOT)}`
- Satellite image: `{rel(sat_path, PACKAGE_ROOT)}`
- Surface mask: `{rel(mask_path, PACKAGE_ROOT)}`
- Map legend: `{rel(legend_path, PACKAGE_ROOT)}`
- Layers config: `{rel(layers_path, PACKAGE_ROOT)}`
- Config: `{rel(config_path, PACKAGE_ROOT)}`

Save Terrain Builder project immediately as:

`P:\\{meta['terrainName']}\\{meta['terrainName']}.pew`
""",
        encoding="ascii",
    )
    return out


def parse_args():
    parser = argparse.ArgumentParser(description="Create Terrain Builder import files for a processed terrain export.")
    parser.add_argument("--export-root", default=str(EXPORT_ROOT))
    parser.add_argument("--package-root", default=None)
    return parser.parse_args()


def configure_from_args(args, meta):
    global EXPORT_ROOT, META_FILE, PACKAGE_ROOT, SOURCE_DIR
    EXPORT_ROOT = project_path(args.export_root)
    META_FILE = EXPORT_ROOT / "terrain_builder_export_metadata.json"
    PACKAGE_ROOT = project_path(args.package_root) if args.package_root else ROOT / "terrain" / "terrain-builder" / meta["terrainName"]
    SOURCE_DIR = PACKAGE_ROOT / "source"


def main():
    args = parse_args()
    meta_path = project_path(args.export_root) / "terrain_builder_export_metadata.json"
    meta = read_json(meta_path)
    configure_from_args(args, meta)
    for folder in ["data", "world", "source", "ce", "navmesh"]:
        (PACKAGE_ROOT / folder).mkdir(parents=True, exist_ok=True)
    asc = write_asc(meta)
    mask, sat, legend = create_mask_satellite_and_legend(meta)
    layers = write_layers_cfg(meta)
    config = write_config(meta)
    write_readme(meta, asc, mask, sat, legend, layers, config)
    print(f"Wrote Terrain Builder package to {PACKAGE_ROOT}")
    print(f"Height ASC: {asc}")
    print(f"Satellite: {sat}")
    print(f"Mask: {mask}")


if __name__ == "__main__":
    main()


