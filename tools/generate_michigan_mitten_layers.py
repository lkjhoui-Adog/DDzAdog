import argparse
from pathlib import Path
import shutil

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MITTEN = ROOT / "workdrive" / "MichiganMitten"
MITTEN_LAYERS = MITTEN / "data" / "layers"
MASK = MITTEN / "source" / "michigan_mitten_mask_lco.png"
SATELLITE = MITTEN / "source" / "michigan_mitten_sat_lco.png"

SATELLITE_SIZE = 4096
TILE_SIZE = 512
TILE_COUNT = SATELLITE_SIZE // TILE_SIZE
WORLD_SIZE_METERS = 40960.0
TILE_WORLD_SIZE_METERS = WORLD_SIZE_METERS / TILE_COUNT
FULL_SURFACE_SUFFIX = "L00"


def fmt(value: float) -> str:
    if abs(value) < 0.0000000000005:
        return "0"
    text = f"{value:.12f}"
    return text.rstrip("0").rstrip(".")


def terrainx_rvmat(
    satellite_name: str,
    mask_name: str,
    scale: float,
    position_x: float,
    position_y: float,
) -> str:
    replacements = {
        "__SATELLITE__": satellite_name,
        "__MASK__": mask_name,
        "__SCALE__": fmt(scale),
        "__POS_X__": fmt(position_x),
        "__POS_Y__": fmt(position_y),
    }
    text = """ambient[]={0.9,0.9,0.9,1};
diffuse[]={0.9,0.9,0.9,1};
forcedDiffuse[]={0.02,0.02,0.02,1};
emmisive[]={0,0,0,0};
specular[]={0,0,0,0};
specularPower=0;
class Stage0
{
\ttexture="michiganmitten\\data\\layers\\__SATELLITE__";
\ttexGen=3;
};
class Stage1
{
\ttexture="michiganmitten\\data\\layers\\__MASK__";
\ttexGen=4;
};
class TexGen3
{
\tuvSource="worldPos";
\tclass uvTransform
\t{
\t\taside[]={__SCALE__,0,0};
\t\tup[]={0,0,__SCALE__};
\t\tdir[]={0,-__SCALE__,0};
\t\tpos[]={__POS_X__,__POS_Y__,0};
\t};
};
class TexGen4
{
\tuvSource="worldPos";
\tclass uvTransform
\t{
\t\taside[]={__SCALE__,0,0};
\t\tup[]={0,0,__SCALE__};
\t\tdir[]={0,-__SCALE__,0};
\t\tpos[]={__POS_X__,__POS_Y__,0};
\t};
};
class TexGen0
{
\tuvSource="tex";
\tclass uvTransform
\t{
\t\taside[]={1,0,0};
\t\tup[]={0,1,0};
\t\tdir[]={0,0,1};
\t\tpos[]={0,0,0};
\t};
};
class TexGen1
{
\tuvSource="tex";
\tclass uvTransform
\t{
\t\taside[]={10,0,0};
\t\tup[]={0,10,0};
\t\tdir[]={0,0,10};
\t\tpos[]={0,0,0};
\t};
};
class TexGen2
{
\tuvSource="tex";
\tclass uvTransform
\t{
\t\taside[]={10,0,0};
\t\tup[]={0,10,0};
\t\tdir[]={0,0,10};
\t\tpos[]={0,0,0};
\t};
};
PixelShaderID="TerrainX";
VertexShaderID="Terrain";
class Stage2
{
\ttexture="#(rgb,1,1,1)color(0.5,0.5,0.5,1,cdt)";
\ttexGen=0;
};
class Stage3
{
\ttexture="dz\\surfaces\\data\\terrain\\cp_grass_nopx.paa";
\ttexGen=1;
};
class Stage4
{
\ttexture="dz\\surfaces\\data\\terrain\\cp_grass_ca.paa";
\ttexGen=2;
};
class Stage5 { texture=""; texGen=1; };
class Stage6 { texture=""; texGen=2; };
class Stage7 { texture=""; texGen=1; };
class Stage8 { texture=""; texGen=2; };
class Stage9 { texture=""; texGen=1; };
class Stage10 { texture=""; texGen=2; };
class Stage11 { texture=""; texGen=1; };
class Stage12 { texture=""; texGen=2; };
class Stage13 { texture=""; texGen=1; };
class Stage14 { texture=""; texGen=2; };
"""
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text


def prepare_images() -> tuple[Path, Path, Path, Path]:
    MITTEN_LAYERS.mkdir(parents=True, exist_ok=True)
    expected_size = (SATELLITE_SIZE, SATELLITE_SIZE)
    with Image.open(SATELLITE) as satellite:
        if satellite.size != expected_size:
            raise ValueError(f"Satellite image must be {expected_size}, got {satellite.size}")
    with Image.open(MASK) as mask:
        if mask.size != expected_size:
            raise ValueError(f"Surface mask must be {expected_size}, got {mask.size}")

    satellite_target = MITTEN_LAYERS / "S_full_lco.png"
    source_mask_target = MITTEN_LAYERS / "M_full_source_lco.png"
    full_mask_target = MITTEN_LAYERS / "M_full_lca.png"
    tile_mask_target = MITTEN_LAYERS / "M_base_lca.png"
    shutil.copy2(SATELLITE, satellite_target)
    shutil.copy2(MASK, source_mask_target)

    # Opaque black selects the first TerrainX detail layer.
    Image.new("RGBA", expected_size, (0, 0, 0, 255)).save(full_mask_target)
    Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 255)).save(tile_mask_target)
    return satellite_target, source_mask_target, full_mask_target, tile_mask_target


def generate_satellite_tiles() -> int:
    created = 0
    with Image.open(SATELLITE) as source:
        image = source.convert("RGB")
        for tile_x in range(TILE_COUNT):
            for tile_y in range(TILE_COUNT):
                left = tile_x * TILE_SIZE
                upper = tile_y * TILE_SIZE
                crop = image.crop((left, upper, left + TILE_SIZE, upper + TILE_SIZE))
                crop.save(MITTEN_LAYERS / f"S_{tile_x:03d}_{tile_y:03d}_lco.png")
                created += 1
    return created


def generate_tiled_surface_rvmats() -> int:
    for stale in MITTEN_LAYERS.glob("P_*.rvmat"):
        stale.unlink()

    scale = 1.0 / TILE_WORLD_SIZE_METERS
    created = 0
    for tile_x in range(TILE_COUNT):
        for tile_y in range(TILE_COUNT):
            text = terrainx_rvmat(
                f"s_{tile_x:03d}_{tile_y:03d}_lco.paa",
                "m_base_lca.paa",
                scale,
                -float(tile_x),
                float(TILE_COUNT - tile_y),
            )
            output = MITTEN_LAYERS / f"P_{tile_x:03d}-{tile_y:03d}_{FULL_SURFACE_SUFFIX}.rvmat"
            output.write_text(text, encoding="ascii", newline="\n")
            created += 1
    return created


def generate_full_surface_rvmat() -> Path:
    text = terrainx_rvmat(
        "s_full_lco.paa",
        "m_full_lca.paa",
        1.0 / WORLD_SIZE_METERS,
        0.0,
        1.0,
    )
    output = MITTEN_LAYERS / f"P_full_{FULL_SURFACE_SUFFIX}.rvmat"
    output.write_text(text, encoding="ascii", newline="\n")
    return output


def main() -> None:
    global MITTEN, MITTEN_LAYERS, MASK, SATELLITE
    parser = argparse.ArgumentParser(description="Generate tiled TerrainX layers for MichiganMitten.")
    parser.add_argument("--project-root", default=str(MITTEN))
    args = parser.parse_args()
    MITTEN = Path(args.project_root).resolve()
    MITTEN_LAYERS = MITTEN / "data" / "layers"
    MASK = MITTEN / "source" / "michigan_mitten_mask_lco.png"
    SATELLITE = MITTEN / "source" / "michigan_mitten_sat_lco.png"

    satellite, source_mask, full_mask, tile_mask = prepare_images()
    satellite_tiles = generate_satellite_tiles()
    rvmats = generate_tiled_surface_rvmats()
    full_surface = generate_full_surface_rvmat()
    print(f"Prepared full satellite image: {satellite}")
    print(f"Preserved source classification mask: {source_mask}")
    print(f"Prepared full fallback mask: {full_mask}")
    print(f"Prepared tile mask: {tile_mask}")
    print(f"Generated {satellite_tiles} satellite PNG tiles")
    print(f"Generated {rvmats} tiled TerrainX RVMAT files")
    print(f"Generated full-world fallback RVMAT: {full_surface}")


if __name__ == "__main__":
    main()
