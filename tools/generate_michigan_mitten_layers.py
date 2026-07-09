from pathlib import Path
import re

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MITTEN = ROOT / "workdrive" / "MichiganMitten"
SURVIVAL_LAYERS = ROOT / "workdrive" / "MichiganSurvival" / "data" / "layers"
MITTEN_LAYERS = MITTEN / "data" / "layers"
MASK = MITTEN / "source" / "michigan_mitten_mask_lco.png"

TILE_SIZE = 512
TILE_COUNT = 9
TILE_STEP = 448
TEX_SCALE = 0.00080001028
POS_START_X = 0.03125
POS_START_Y = 8.03125
POS_STEP = 0.9375


def fmt(value: float) -> str:
    text = f"{value:.7f}"
    return text.rstrip("0").rstrip(".")


def generate_mask_tiles() -> int:
    MITTEN_LAYERS.mkdir(parents=True, exist_ok=True)
    image = Image.open(MASK).convert("RGB")
    created = 0
    for row in range(TILE_COUNT):
        for col in range(TILE_COUNT):
            left = col * TILE_STEP
            upper = row * TILE_STEP
            crop = image.crop((left, upper, left + TILE_SIZE, upper + TILE_SIZE))
            crop.save(MITTEN_LAYERS / f"M_{row:03d}_{col:03d}_lco.png")
            created += 1
    return created


def collect_templates() -> dict[str, str]:
    templates: dict[str, str] = {}
    for path in sorted(SURVIVAL_LAYERS.glob("P_*.rvmat")):
        match = re.match(r"^P_\d{3}-\d{3}_(.+)\.rvmat$", path.name)
        if not match:
            continue
        suffix = match.group(1)
        templates.setdefault(suffix, path.read_text(encoding="ascii"))
    if not templates:
        raise RuntimeError(f"No RVMAT templates found in {SURVIVAL_LAYERS}")
    return templates


def replace_first_two_pos_blocks(text: str, row: int, col: int) -> str:
    x_pos = POS_START_X - (row * POS_STEP)
    y_pos = POS_START_Y - (col * POS_STEP)
    replacement = f"pos[]={{{fmt(x_pos)},{fmt(y_pos)},0}};"

    def repl(match: re.Match[str]) -> str:
        repl.count += 1
        return replacement if repl.count <= 2 else match.group(0)

    repl.count = 0
    return re.sub(r"pos\[\]=\{[^}]+\};", repl, text)


def rewrite_template(template: str, row: int, col: int) -> str:
    text = template.replace("michigansurvival", "michiganmitten")
    text = re.sub(
        r's_\d{3}_\d{3}_lco\.paa',
        f"s_{row:03d}_{col:03d}_lco.paa",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r'm_\d{3}_\d{3}_lco\.paa',
        f"m_{row:03d}_{col:03d}_lco.paa",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"aside\[\]=\{0\.00080001028,0,0\};",
        f"aside[]={{{TEX_SCALE},0,0}};",
        text,
    )
    text = re.sub(
        r"up\[\]=\{0,0,0\.00080001028\};",
        f"up[]={{0,0,{TEX_SCALE}}};",
        text,
    )
    text = re.sub(
        r"dir\[\]=\{0,-0\.00080001028,0\};",
        f"dir[]={{0,-{TEX_SCALE},0}};",
        text,
    )
    return replace_first_two_pos_blocks(text, row, col)


def generate_rvmats() -> int:
    templates = collect_templates()
    for stale in MITTEN_LAYERS.glob("P_*.rvmat"):
        stale.unlink()

    created = 0
    for row in range(TILE_COUNT):
        for col in range(TILE_COUNT):
            for suffix, template in templates.items():
                rvmat = rewrite_template(template, row, col)
                out = MITTEN_LAYERS / f"P_{row:03d}-{col:03d}_{suffix}.rvmat"
                out.write_text(rvmat, encoding="ascii", newline="\n")
                created += 1
    return created


def main() -> None:
    mask_tiles = generate_mask_tiles()
    rvmats = generate_rvmats()
    print(f"Generated {mask_tiles} mask PNG tiles")
    print(f"Generated {rvmats} layer RVMAT files")


if __name__ == "__main__":
    main()
