#!/usr/bin/env python3
"""Build a conservative Central Economy population for MichiganMitten."""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image

from embed_michigan_roads_in_wrp import (
    HeightGrid,
    locate_object_section_without_empty_requirement,
    parse_embedded_objects,
)


WORLD_SIZE = 40960.0
LAND_THRESHOLD = 1.0
BUILDING_PREFIX = "michiganmitten_buildings\\models\\buildings\\"
LANDMARK_PREFIX = "michiganmitten_landmarks\\models\\landmarks\\"
SELECTED_EVENTS = {
    "AmbientFox",
    "AmbientHare",
    "AmbientHen",
    "AnimalBear",
    "AnimalDeer",
    "AnimalRoeDeer",
    "AnimalWildBoar",
    "AnimalWolf",
    "InfectedArmy",
    "InfectedArmyHard",
    "InfectedCity",
    "InfectedCityTier1",
    "InfectedFirefighter",
    "InfectedIndustrial",
    "InfectedMedic",
    "InfectedPolice",
    "InfectedPoliceHard",
    "InfectedPrisoner",
    "InfectedSolitude",
    "InfectedVillage",
    "InfectedVillageTier1",
    "ItemPlanks",
    "Loot",
    "StaticHeliCrash",
    "TrajectoryApple",
    "TrajectoryCanina",
    "TrajectoryConiferous",
    "TrajectoryDeciduous",
    "TrajectoryHumus",
    "TrajectoryPear",
    "TrajectoryPlum",
    "TrajectorySambucus",
    "TrajectoryStones",
    "VehicleBoat",
    "VehicleCivilianSedan",
    "VehicleHatchback02",
    "VehicleOffroad02",
    "VehicleOffroadHatchback",
    "VehicleSedan02",
    "VehicleTruck01",
}
VEHICLE_TARGETS = {
    "VehicleCivilianSedan": (24, "city"),
    "VehicleHatchback02": (22, "city"),
    "VehicleSedan02": (20, "city"),
    "VehicleOffroadHatchback": (20, "rural"),
    "VehicleOffroad02": (16, "rural"),
    "VehicleTruck01": (12, "truck"),
}
ANIMAL_NOMINALS = {
    "AmbientFox": 8,
    "AmbientHare": 12,
    "AmbientHen": 0,
    "AnimalBear": 3,
    "AnimalDeer": 8,
    "AnimalRoeDeer": 8,
    "AnimalWildBoar": 6,
    "AnimalWolf": 4,
}
ANIMAL_COUNTS = {
    "bear_territories.xml": 6,
    "wolf_territories.xml": 10,
    "red_deer_territories.xml": 22,
    "roe_deer_territories.xml": 20,
    "wild_boar_territories.xml": 18,
    "fox_territories.xml": 20,
    "hare_territories.xml": 20,
}
EMPTY_TERRITORIES = {
    "cattle_territories.xml",
    "domestic_animals_territories.xml",
    "hen_territories.xml",
    "pig_territories.xml",
    "sheep_goat_territories.xml",
}
FOREST_COLOR = (25, 95, 45)


def read_json(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_xml(path: Path, root: ET.Element) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="    ")
    body = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    path.write_text('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + body + "\n", encoding="utf-8")


def basename(path: str) -> str:
    return path.replace("/", "\\").rsplit("\\", 1)[-1].lower()


def yaw_from_matrix(matrix: list[float] | tuple[float, ...]) -> float:
    return math.degrees(math.atan2(-float(matrix[2]), float(matrix[0]))) % 360.0


def signed_angle(value: float) -> float:
    return ((value + 180.0) % 360.0) - 180.0


def load_manifests(building_path: Path, landmark_path: Path) -> tuple[dict, dict]:
    building = read_json(building_path).get("models")
    landmark = read_json(landmark_path).get("models")
    if not isinstance(building, list) or not isinstance(landmark, list):
        raise ValueError("Building or landmark model manifest is invalid")
    building_by_model = {str(item["model"]).lower(): item for item in building}
    landmark_by_model = {str(item["model"]).lower(): item for item in landmark}
    return building_by_model, landmark_by_model


def embedded_custom_groups(
    wrp: Path,
    building_by_model: dict,
    landmark_by_model: dict,
) -> tuple[list[dict], HeightGrid, dict]:
    blob = wrp.resolve().read_bytes()
    layout, heights, _ = locate_object_section_without_empty_requirement(blob)
    embedded = parse_embedded_objects(blob, layout)
    groups: list[dict] = []
    unknown: set[str] = set()
    counts = Counter()
    for item in embedded:
        normalized = str(item["path"]).replace("/", "\\").lower()
        metadata = None
        group_type = None
        if normalized.startswith(BUILDING_PREFIX):
            metadata = building_by_model.get(basename(normalized))
            group_type = "building"
        elif normalized.startswith(LANDMARK_PREFIX):
            metadata = landmark_by_model.get(basename(normalized))
            group_type = "landmark"
        else:
            continue
        if metadata is None:
            unknown.add(basename(normalized))
            continue
        matrix = [float(value) for value in item["matrix"]]
        groups.append(
            {
                "objectId": int(item["id"]),
                "model": basename(normalized),
                "className": str(metadata["className"]),
                "type": group_type,
                "kind": str(metadata.get("kind", "landmark")),
                "family": str(metadata.get("family", "landmark")),
                "zone": str(metadata.get("zone", "downtown")),
                "width": float(metadata.get("width", (metadata.get("footprintMeters") or [50.0])[0])),
                "depth": float(metadata.get("depth", (metadata.get("footprintMeters") or [50.0, 40.0])[1])),
                "floors": int(metadata.get("floors", 1)),
                "position": [matrix[9], matrix[10], matrix[11]],
                "yaw": yaw_from_matrix(matrix),
            }
        )
        counts[group_type] += 1
    if unknown:
        raise ValueError(f"Unknown custom models in WRP: {sorted(unknown)}")
    return groups, HeightGrid(heights, layout.terrain_cell_size), {
        "embeddedObjects": len(embedded),
        "customGroups": len(groups),
        "groupTypes": dict(counts),
    }


def usages_for(kind: str, family: str, zone: str) -> list[str]:
    text = f"{kind} {family} {zone}".lower()
    if any(word in text for word in ("military", "barracks", "army")):
        return ["Military"]
    if "prison" in text or "correction" in text:
        return ["Prison", "Police"]
    if "police" in text:
        return ["Police"]
    if any(word in text for word in ("research", "laboratory", "biology", "conservation")):
        return ["Medic", "Industrial", "Office"]
    if any(word in text for word in ("hospital", "clinic", "quarantine", "medical")):
        return ["Medic"]
    if "fire" in text:
        return ["Firefighter", "Industrial"]
    if any(word in text for word in ("camp", "ranger", "hunting")):
        return ["Hunting", "Village"]
    if any(word in text for word in ("marina", "bait", "coast", "carferry")):
        return ["Coast", "Hunting"]
    if "school" in text:
        return ["School", "Town"]
    if any(word in text for word in ("farm", "barn", "grain", "orchard")):
        return ["Farm"]
    if any(word in text for word in ("airport", "factory", "warehouse", "industrial", "utility", "garage", "works", "hangar", "repair", "dealer", "gas station")):
        return ["Industrial"]
    if any(word in text for word in ("cabin", "cottage", "house", "bungalow", "ranch", "duplex", "residential")):
        return ["Village"]
    if any(word in text for word in ("church", "historic", "heritage", "fort")):
        return ["Historical", "Town"]
    if any(word in text for word in ("library", "office", "court", "hall", "capitol")):
        return ["Office", "Town"]
    return ["Town"]


def categories_for(usages: list[str], kind: str) -> list[str]:
    usage = set(usages)
    if "Military" in usage:
        return ["weapons", "clothes", "tools", "containers"]
    if "Prison" in usage:
        return ["clothes", "tools", "weapons", "containers"]
    if "Police" in usage:
        return ["weapons", "clothes", "tools"]
    if "Medic" in usage:
        return ["clothes", "tools", "containers"]
    if "Hunting" in usage:
        return ["weapons", "food", "tools", "clothes", "containers"]
    if "Coast" in usage:
        return ["food", "tools", "containers", "clothes"]
    if "School" in usage:
        return ["clothes", "food", "tools", "containers"]
    if "Farm" in usage:
        return ["food", "tools", "containers"]
    if "Industrial" in usage:
        return ["tools", "containers", "clothes"]
    if "Village" in usage:
        return ["food", "clothes", "tools"]
    if any(word in kind.lower() for word in ("store", "market", "grocery", "diner", "pub", "cafe")):
        return ["food", "clothes", "containers"]
    return ["clothes", "food", "tools", "containers"]


def model_loot_points(group: dict) -> list[tuple[float, float, float]]:
    width = max(8.0, float(group["width"]))
    depth = max(8.0, float(group["depth"]))
    floors = 1 if group["type"] == "landmark" else max(1, min(int(group["floors"]), 4))
    inset_x = min(width * 0.26, max(2.2, width * 0.5 - 2.5))
    inset_z = min(depth * 0.26, max(2.2, depth * 0.5 - 2.5))
    base = [
        (-inset_x, -inset_z),
        (inset_x, -inset_z),
        (-inset_x, inset_z),
        (inset_x, inset_z),
        (0.0, 0.0),
    ]
    points: list[tuple[float, float, float]] = []
    for floor in range(floors):
        y = 0.18 + floor * 3.2
        for x, z in base:
            points.append((x, y, z))
    maximum = 8 if group["type"] == "landmark" else min(14, 5 + floors * 2)
    return points[:maximum]


def build_map_groups(groups: list[dict]) -> tuple[ET.Element, ET.Element, dict]:
    representative: dict[str, dict] = {}
    for group in groups:
        representative.setdefault(group["className"], group)

    prototype = ET.Element("prototype")
    defaults = ET.SubElement(prototype, "defaults")
    ET.SubElement(defaults, "default", name="group", lootmax="8")
    ET.SubElement(defaults, "default", name="container", lootmax="6")
    ET.SubElement(defaults, "default", name="keepInvalidPoints", enabled="yes")
    point_total = 0
    for class_name in sorted(representative):
        item = representative[class_name]
        usages = usages_for(item["kind"], item["family"], item["zone"])
        points = model_loot_points(item)
        lootmax = min(12, max(3, len(points) // 2))
        group_element = ET.SubElement(prototype, "group", name=class_name, lootmax=str(lootmax))
        for usage in usages:
            ET.SubElement(group_element, "usage", name=usage)
        container = ET.SubElement(group_element, "container", name="lootFloor", lootmax=str(lootmax))
        for category in categories_for(usages, item["kind"]):
            ET.SubElement(container, "category", name=category)
        ET.SubElement(container, "tag", name="ground")
        ET.SubElement(container, "tag", name="floor")
        for x, y, z in points:
            ET.SubElement(
                container,
                "point",
                pos=f"{x:.3f} {y:.3f} {z:.3f}",
                range="0.850",
                height="1.700",
                flags="32",
            )
        point_total += len(points)

    positions = ET.Element("map")
    for item in sorted(groups, key=lambda value: value["objectId"]):
        x, y, z = item["position"]
        rpy_z = signed_angle(-item["yaw"])
        angle = signed_angle(90.0 - rpy_z)
        ET.SubElement(
            positions,
            "group",
            name=item["className"],
            pos=f"{x:.3f} {y:.3f} {z:.3f}",
            rpy=f"0.000 0.000 {rpy_z:.3f}",
            a=f"{angle:.3f}",
        )
    return prototype, positions, {
        "groupDefinitions": len(representative),
        "groupPlacements": len(groups),
        "lootPoints": point_total,
    }


def coordinate_pairs(geometry: dict) -> list[tuple[float, float]]:
    coordinates = geometry.get("coordinates") or []
    geometry_type = geometry.get("type")
    if geometry_type == "LineString":
        return [(float(point[0]), float(point[1])) for point in coordinates]
    if geometry_type == "MultiLineString":
        return [
            (float(point[0]), float(point[1]))
            for line in coordinates
            for point in line
        ]
    return []


def city_centers(road_map: dict) -> dict[str, tuple[float, float]]:
    points: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for feature in road_map.get("features", []):
        properties = feature.get("properties") or {}
        city_id = properties.get("cityId")
        scope = str(properties.get("scope", ""))
        if not city_id or scope not in {"city", "city-structure-fill"}:
            continue
        pairs = coordinate_pairs(feature.get("geometry") or {})
        if pairs:
            points[str(city_id)].extend((pairs[0], pairs[-1], pairs[len(pairs) // 2]))
    if len(points) < 27:
        raise ValueError(f"Only {len(points)} city centers could be derived")
    centers = {}
    for city_id, values in points.items():
        centers[city_id] = (
            sum(point[0] for point in values) / len(values),
            sum(point[1] for point in values) / len(values),
        )
    return centers


def nearest_city(x: float, z: float, centers: dict[str, tuple[float, float]]) -> tuple[str, float]:
    city_id, center = min(
        centers.items(),
        key=lambda item: (x - item[1][0]) ** 2 + (z - item[1][1]) ** 2,
    )
    return city_id, math.hypot(x - center[0], z - center[1])


def infected_zones(groups: list[dict], centers: dict[str, tuple[float, float]]) -> tuple[ET.Element, dict]:
    city_groups: dict[str, list[dict]] = defaultdict(list)
    for group in groups:
        x, _, z = group["position"]
        city_id, distance = nearest_city(x, z, centers)
        if distance <= 2600.0:
            city_groups[city_id].append(group)

    root = ET.Element("territory-type")
    general = ET.SubElement(root, "territory", color="2193199729")
    zone_counts = Counter()
    metro = {"Detroit", "GrandRapids", "Lansing", "Flint", "AnnArbor", "Hometown"}
    for city_id in sorted(centers):
        buildings = city_groups.get(city_id, [])
        cells: dict[tuple[int, int], list[dict]] = defaultdict(list)
        for item in buildings:
            x, _, z = item["position"]
            cells[(round(x / 260.0), round(z / 260.0))].append(item)
        ranked = sorted(cells.values(), key=lambda values: (-len(values), values[0]["objectId"]))
        target = 9 if city_id in metro else 5
        selected = ranked[:target]
        if not selected:
            center_x, center_z = centers[city_id]
            selected = [[{"position": [center_x, 0.0, center_z], "objectId": 0}]]
        for index, cell in enumerate(selected):
            x = sum(item["position"][0] for item in cell) / len(cell)
            z = sum(item["position"][2] for item in cell) / len(cell)
            event = "InfectedCity" if city_id in metro and index < 5 else "InfectedVillage"
            minimum = max(2, min(8, 2 + len(cell) // 5))
            maximum = max(minimum + 2, min(14, minimum + 4))
            radius = max(55, min(120, 50 + len(cell) * 2))
            ET.SubElement(
                general,
                "zone",
                name=event,
                smin="0",
                smax="0",
                dmin=str(minimum),
                dmax=str(maximum),
                x=f"{x:.3f}",
                z=f"{z:.3f}",
                r=str(radius),
            )
            zone_counts[event] += 1

    specialized = {
        "police": "InfectedPolice",
        "fire": "InfectedFirefighter",
        "clinic": "InfectedMedic",
        "hospital": "InfectedMedic",
        "military": "InfectedArmyHard",
        "barracks": "InfectedArmy",
        "prison": "InfectedPrisoner",
        "factory": "InfectedIndustrial",
        "warehouse": "InfectedIndustrial",
        "research": "InfectedIndustrial",
    }
    special_territory = ET.SubElement(root, "territory", color="4282664004")
    occupied: list[tuple[float, float, str]] = []
    for item in sorted(groups, key=lambda value: value["objectId"]):
        descriptor = f"{item['kind']} {item['family']} {item['className']}".lower()
        event = next((value for key, value in specialized.items() if key in descriptor), None)
        if event is None:
            continue
        x, _, z = item["position"]
        if any(other_event == event and math.hypot(x - ox, z - oz) < 180.0 for ox, oz, other_event in occupied):
            continue
        ET.SubElement(
            special_territory,
            "zone",
            name=event,
            smin="0",
            smax="0",
            dmin="2",
            dmax="6" if event not in {"InfectedArmyHard", "InfectedPrisoner"} else "8",
            x=f"{x:.3f}",
            z=f"{z:.3f}",
            r="65",
        )
        occupied.append((x, z, event))
        zone_counts[event] += 1
    return root, {"zones": sum(zone_counts.values()), "byEvent": dict(zone_counts)}


def is_forest(mask: Image.Image, x: float, z: float) -> bool:
    px = min(mask.width - 1, max(0, int(x / WORLD_SIZE * mask.width)))
    py = min(mask.height - 1, max(0, int((WORLD_SIZE - z) / WORLD_SIZE * mask.height)))
    value = mask.getpixel((px, py))
    rgb = tuple(int(component) for component in value[:3])
    return sum((rgb[index] - FOREST_COLOR[index]) ** 2 for index in range(3)) <= 45 ** 2


def spread_select(candidates: list[dict], count: int, minimum_distance: float) -> list[dict]:
    selected: list[dict] = []
    for candidate in candidates:
        x, z = candidate["x"], candidate["z"]
        if all(math.hypot(x - item["x"], z - item["z"]) >= minimum_distance for item in selected):
            selected.append(candidate)
            if len(selected) >= count:
                break
    return selected


def forest_candidates(
    mask: Image.Image,
    height_grid: HeightGrid,
    centers: dict[str, tuple[float, float]],
    seed: int,
) -> list[dict]:
    rng = random.Random(seed)
    candidates = []
    for z_base in range(500, int(WORLD_SIZE), 500):
        for x_base in range(500, int(WORLD_SIZE), 500):
            x = x_base + rng.uniform(-180.0, 180.0)
            z = z_base + rng.uniform(-180.0, 180.0)
            if not is_forest(mask, x, z) or height_grid.sample(x, z) < LAND_THRESHOLD:
                continue
            city_distance = min(math.hypot(x - cx, z - cz) for cx, cz in centers.values())
            if city_distance < 700.0:
                continue
            candidates.append({"x": x, "z": z, "cityDistance": city_distance})
    rng.shuffle(candidates)
    candidates.sort(key=lambda item: (-item["cityDistance"], item["x"], item["z"]))
    return candidates


def animal_territory(position: dict, color: str) -> ET.Element:
    territory = ET.Element("territory", color=color)
    x, z = position["x"], position["z"]
    ET.SubElement(territory, "zone", name="Rest", smin="0", smax="0", dmin="0", dmax="0", x=f"{x:.3f}", z=f"{z:.3f}", r="150")
    ET.SubElement(territory, "zone", name="HuntingGround", smin="0", smax="0", dmin="0", dmax="0", x=f"{x + 120.0:.3f}", z=f"{z - 80.0:.3f}", r="260")
    ET.SubElement(territory, "zone", name="HuntingGround", smin="0", smax="0", dmin="0", dmax="0", x=f"{x - 140.0:.3f}", z=f"{z + 95.0:.3f}", r="220")
    return territory


def build_animal_files(candidates: list[dict]) -> tuple[dict[str, ET.Element], dict]:
    roots: dict[str, ET.Element] = {}
    counts = {}
    offset = 0
    colors = ["4291611852", "4288445520", "4282664004", "4294901760"]
    for file_index, (filename, target) in enumerate(ANIMAL_COUNTS.items()):
        root = ET.Element("territory-type")
        source = candidates[offset:] + candidates[:offset]
        selected = spread_select(source, target, 900.0 if target <= 10 else 650.0)
        if len(selected) < target:
            selected = spread_select(source, target, 450.0)
        for position in selected:
            root.append(animal_territory(position, colors[file_index % len(colors)]))
        roots[filename] = root
        counts[filename] = len(selected)
        offset = (offset + max(7, target)) % max(1, len(candidates))
    for filename in sorted(EMPTY_TERRITORIES):
        roots[filename] = ET.Element("territory-type")
        counts[filename] = 0
    return roots, counts


def road_candidates(objects_path: Path, height_grid: HeightGrid) -> list[dict]:
    objects = read_json(objects_path).get("Objects")
    if not isinstance(objects, list):
        raise ValueError("Road object payload is invalid")
    candidates = []
    for index, item in enumerate(objects):
        name = str(item.get("name", ""))
        lower = name.lower()
        if not name.startswith("MI_Road_") or any(word in lower for word in ("support", "tower", "cable", "anchor", "pier")):
            continue
        position = item.get("pos") or []
        if len(position) != 3:
            continue
        x, z = float(position[0]), float(position[2])
        if height_grid.sample(x, z) < LAND_THRESHOLD:
            continue
        if "dirt" in lower:
            road_type = "dirt"
        elif "freeway" in lower:
            road_type = "freeway"
        elif "rural" in lower:
            road_type = "rural"
        else:
            road_type = "city"
        candidates.append(
            {
                "index": index,
                "x": x,
                "z": z,
                "a": float((item.get("ypr") or [0.0])[0]) % 360.0,
                "type": road_type,
            }
        )
    return candidates


def deterministic_road_subset(candidates: list[dict], kinds: set[str], seed: int) -> list[dict]:
    selected = [item for item in candidates if item["type"] in kinds]
    selected.sort(key=lambda item: ((item["index"] * 2654435761 + seed) & 0xFFFFFFFF, item["index"]))
    return selected


def boat_candidates(height_grid: HeightGrid, seed: int) -> list[dict]:
    rng = random.Random(seed)
    candidates = []
    for z in range(350, int(WORLD_SIZE), 300):
        for x in range(350, int(WORLD_SIZE), 300):
            sample_x = x + rng.uniform(-80.0, 80.0)
            sample_z = z + rng.uniform(-80.0, 80.0)
            if height_grid.sample(sample_x, sample_z) > -1.0:
                continue
            near_land = any(
                height_grid.sample(sample_x + dx, sample_z + dz) >= LAND_THRESHOLD
                for dx, dz in ((35, 0), (-35, 0), (0, 35), (0, -35), (55, 0), (-55, 0), (0, 55), (0, -55))
            )
            if near_land:
                candidates.append({"x": sample_x, "z": sample_z, "a": rng.uniform(0.0, 360.0)})
    rng.shuffle(candidates)
    return candidates


def build_event_spawns(
    roads: list[dict],
    height_grid: HeightGrid,
    forest: list[dict],
    seed: int,
) -> tuple[ET.Element, dict]:
    root = ET.Element("eventposdef")
    counts = {}
    occupied: list[dict] = []
    for event_index, (event_name, (target, profile)) in enumerate(VEHICLE_TARGETS.items()):
        if profile == "city":
            source = deterministic_road_subset(roads, {"city"}, seed + event_index)
        elif profile == "truck":
            source = deterministic_road_subset(roads, {"freeway", "rural"}, seed + event_index)
        else:
            source = deterministic_road_subset(roads, {"dirt", "rural"}, seed + event_index)
        source = [
            item for item in source
            if all(math.hypot(item["x"] - used["x"], item["z"] - used["z"]) >= 350.0 for used in occupied)
        ]
        selected = spread_select(source, target, 850.0)
        event = ET.SubElement(root, "event", name=event_name)
        for item in selected:
            ET.SubElement(event, "pos", x=f"{item['x']:.3f}", z=f"{item['z']:.3f}", a=f"{item['a']:.3f}")
        counts[event_name] = len(selected)
        occupied.extend(selected)

    boats = spread_select(boat_candidates(height_grid, seed + 77), 24, 900.0)
    event = ET.SubElement(root, "event", name="VehicleBoat")
    for item in boats:
        ET.SubElement(event, "pos", x=f"{item['x']:.3f}", z=f"{item['z']:.3f}", a=f"{item['a']:.3f}")
    counts["VehicleBoat"] = len(boats)

    helis = spread_select(forest, 28, 1100.0)
    event = ET.SubElement(root, "event", name="StaticHeliCrash")
    ET.SubElement(event, "zone", smin="1", smax="2", dmin="2", dmax="4", r="45")
    for item in helis:
        ET.SubElement(event, "pos", x=f"{item['x']:.3f}", z=f"{item['z']:.3f}", a="-1")
    counts["StaticHeliCrash"] = len(helis)
    return root, counts


def selected_events(official_events: Path) -> tuple[ET.Element, dict]:
    source_root = ET.parse(official_events.resolve()).getroot()
    by_name = {event.attrib.get("name"): event for event in source_root.findall("event")}
    missing = sorted(SELECTED_EVENTS - set(by_name))
    if missing:
        raise ValueError(f"Official event file is missing: {missing}")
    root = ET.Element("events")
    for name in sorted(SELECTED_EVENTS):
        event = copy.deepcopy(by_name[name])
        if name.startswith("Vehicle"):
            nominal = event.find("nominal")
            minimum = event.find("min")
            maximum = event.find("max")
            target = VEHICLE_TARGETS.get(name, (12, ""))[0]
            if nominal is not None:
                nominal.text = str(max(2, min(target // 2, 10)))
            if minimum is not None:
                minimum.text = str(max(1, min(target // 3, 6)))
            if maximum is not None:
                maximum.text = str(max(3, min(target // 2 + 2, 12)))
        if name in ANIMAL_NOMINALS:
            nominal = event.find("nominal")
            if nominal is None:
                raise ValueError(f"Official event {name} has no nominal value")
            nominal.text = str(ANIMAL_NOMINALS[name])
        root.append(event)
    return root, {"eventDefinitions": len(SELECTED_EVENTS), "names": sorted(SELECTED_EVENTS)}


def adjusted_globals(source: Path) -> ET.Element:
    root = ET.parse(source.resolve()).getroot()
    values = {
        "AnimalMaxCount": "120",
        "InitialSpawn": "80",
        "SpawnInitial": "900",
        "ZombieMaxCount": "420",
        "ZoneSpawnDist": "300",
    }
    found = set()
    for variable in root.findall("var"):
        name = variable.attrib.get("name")
        if name in values:
            variable.set("value", values[name])
            found.add(name)
    if found != set(values):
        raise ValueError(f"Globals file is missing variables: {sorted(set(values) - found)}")
    return root


def empty_map_root() -> ET.Element:
    return ET.Element("map")


def empty_event_groups() -> ET.Element:
    return ET.Element("eventgroupdef")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wrp", required=True, type=Path)
    parser.add_argument("--road-objects", required=True, type=Path)
    parser.add_argument("--road-map", required=True, type=Path)
    parser.add_argument("--building-manifest", required=True, type=Path)
    parser.add_argument("--landmark-manifest", required=True, type=Path)
    parser.add_argument("--mask", required=True, type=Path)
    parser.add_argument("--official-mission", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=26099)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    building_by_model, landmark_by_model = load_manifests(args.building_manifest, args.landmark_manifest)
    groups, height_grid, embedded_report = embedded_custom_groups(args.wrp, building_by_model, landmark_by_model)
    prototype, positions, loot_report = build_map_groups(groups)
    road_map = read_json(args.road_map)
    centers = city_centers(road_map)
    zombies, zombie_report = infected_zones(groups, centers)
    mask = Image.open(args.mask.resolve()).convert("RGB")
    forest = forest_candidates(mask, height_grid, centers, args.seed)
    animal_roots, animal_report = build_animal_files(forest)
    roads = road_candidates(args.road_objects, height_grid)
    event_spawns, spawn_report = build_event_spawns(roads, height_grid, forest, args.seed)
    official_mission = args.official_mission.resolve()
    events, event_report = selected_events(official_mission / "db" / "events.xml")
    globals_root = adjusted_globals(official_mission / "db" / "globals.xml")

    write_xml(output_dir / "mapgroupproto.xml", prototype)
    write_xml(output_dir / "mapgrouppos.xml", positions)
    write_xml(output_dir / "mapgroupcluster.xml", empty_map_root())
    for index in range(1, 5):
        write_xml(output_dir / f"mapgroupcluster{index:02d}.xml", empty_map_root())
    write_xml(output_dir / "mapgroupdirt.xml", empty_map_root())
    write_xml(output_dir / "cfgeventgroups.xml", empty_event_groups())
    write_xml(output_dir / "cfgeventspawns.xml", event_spawns)
    write_xml(output_dir / "db" / "events.xml", events)
    write_xml(output_dir / "db" / "globals.xml", globals_root)
    write_xml(output_dir / "env" / "zombie_territories.xml", zombies)
    for filename, root in animal_roots.items():
        write_xml(output_dir / "env" / filename, root)

    report = {
        "status": "generated",
        "worldSizeMeters": WORLD_SIZE,
        "landThresholdMeters": LAND_THRESHOLD,
        "seed": args.seed,
        "sourceWrp": str(args.wrp.resolve()),
        "officialMission": str(official_mission),
        "outputDir": str(output_dir),
        "embedded": embedded_report,
        "loot": loot_report,
        "cities": {"count": len(centers), "centers": centers},
        "infected": zombie_report,
        "forestCandidates": len(forest),
        "animals": animal_report,
        "eventSpawns": spawn_report,
        "events": event_report,
        "roadCandidates": len(roads),
    }
    write_json(args.report.resolve(), report)
    print(f"MICHIGAN_CE_GROUPS={loot_report['groupPlacements']}")
    print(f"MICHIGAN_CE_LOOT_POINTS={loot_report['lootPoints']}")
    print(f"MICHIGAN_CE_INFECTED_ZONES={zombie_report['zones']}")
    print(f"MICHIGAN_CE_ANIMAL_TERRITORIES={sum(animal_report.values())}")
    print(f"MICHIGAN_CE_EVENT_SPAWNS={sum(spawn_report.values())}")
    print(f"MICHIGAN_CE_REPORT={args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
