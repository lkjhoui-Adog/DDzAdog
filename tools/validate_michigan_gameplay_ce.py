#!/usr/bin/env python3
"""Validate a generated MichiganMitten Central Economy population."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from embed_michigan_roads_in_wrp import HeightGrid, locate_object_section_without_empty_requirement


WORLD_SIZE = 40960.0
LAND_THRESHOLD = 1.0
EXPECTED_ROOTS = {
    "mapgroupproto.xml": "prototype",
    "mapgrouppos.xml": "map",
    "mapgroupcluster.xml": "map",
    "mapgroupcluster01.xml": "map",
    "mapgroupcluster02.xml": "map",
    "mapgroupcluster03.xml": "map",
    "mapgroupcluster04.xml": "map",
    "mapgroupdirt.xml": "map",
    "cfgeventgroups.xml": "eventgroupdef",
    "cfgeventspawns.xml": "eventposdef",
    "db/events.xml": "events",
    "db/globals.xml": "variables",
    "env/zombie_territories.xml": "territory-type",
    "env/bear_territories.xml": "territory-type",
    "env/cattle_territories.xml": "territory-type",
    "env/domestic_animals_territories.xml": "territory-type",
    "env/fox_territories.xml": "territory-type",
    "env/hare_territories.xml": "territory-type",
    "env/hen_territories.xml": "territory-type",
    "env/pig_territories.xml": "territory-type",
    "env/red_deer_territories.xml": "territory-type",
    "env/roe_deer_territories.xml": "territory-type",
    "env/sheep_goat_territories.xml": "territory-type",
    "env/wild_boar_territories.xml": "territory-type",
    "env/wolf_territories.xml": "territory-type",
}
VEHICLE_EVENTS = {
    "VehicleBoat",
    "VehicleCivilianSedan",
    "VehicleHatchback02",
    "VehicleOffroad02",
    "VehicleOffroadHatchback",
    "VehicleSedan02",
    "VehicleTruck01",
}
VALID_USAGES = {
    "Coast",
    "Farm",
    "Firefighter",
    "Historical",
    "Hunting",
    "Industrial",
    "Medic",
    "Military",
    "Office",
    "Police",
    "Prison",
    "School",
    "Town",
    "Village",
}
EXPECTED_GROUP_USAGES = {
    "MI_Building_StatePoliceStation": {"Police"},
    "MI_Building_StateHospital": {"Medic"},
    "MI_Building_StateMilitaryBarracks": {"Military"},
    "MI_Building_StateCampOffice": {"Hunting"},
    "MI_Building_StatePrisonBlock": {"Prison"},
    "MI_Building_StateSchool": {"School"},
    "MI_Building_NorthMarinaBait": {"Coast"},
    "MI_Building_ResearchBiologyLab": {"Medic", "Industrial"},
}
EXPECTED_ANIMAL_NOMINALS = {
    "AmbientFox": 8,
    "AmbientHare": 12,
    "AmbientHen": 0,
    "AnimalBear": 3,
    "AnimalDeer": 8,
    "AnimalRoeDeer": 8,
    "AnimalWildBoar": 6,
    "AnimalWolf": 4,
}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def parse_position(value: str, expected: int) -> list[float]:
    parts = value.split()
    if len(parts) != expected:
        raise ValueError(f"Expected {expected} coordinates, got {value!r}")
    result = [float(part) for part in parts]
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"Non-finite coordinate in {value!r}")
    return result


def load_height_grid(path: Path) -> HeightGrid:
    layout, heights, _ = locate_object_section_without_empty_requirement(path.resolve().read_bytes())
    return HeightGrid(heights, layout.terrain_cell_size)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ce-dir", required=True, type=Path)
    parser.add_argument("--wrp", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--minimum-groups", type=int, default=1500)
    parser.add_argument("--maximum-groups", type=int, default=6000)
    args = parser.parse_args()

    root_dir = args.ce_dir.resolve()
    height_grid = load_height_grid(args.wrp)
    errors: list[str] = []
    warnings: list[str] = []
    parsed: dict[str, ET.Element] = {}
    for relative, expected_root in EXPECTED_ROOTS.items():
        path = root_dir / relative
        if not path.is_file():
            errors.append(f"Missing CE file: {relative}")
            continue
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            errors.append(f"Invalid XML in {relative}: {exc}")
            continue
        if root.tag != expected_root:
            errors.append(f"Wrong root in {relative}: {root.tag}, expected {expected_root}")
        parsed[relative] = root

    events_root = parsed.get("db/events.xml")
    event_names: list[str] = []
    event_nominals: dict[str, int] = {}
    if events_root is not None:
        event_names = [str(item.attrib.get("name", "")) for item in events_root.findall("event")]
        if len(event_names) != len(set(event_names)):
            errors.append("Duplicate event definitions")
        for event in events_root.findall("event"):
            name = event.attrib.get("name", "")
            required = {"nominal", "min", "max", "lifetime", "position", "limit", "active", "children"}
            missing = sorted(required - {child.tag for child in event})
            if missing:
                errors.append(f"Event {name} is missing nodes: {missing}")
            nominal = event.find("nominal")
            if nominal is not None:
                try:
                    event_nominals[name] = int(nominal.text or "")
                except ValueError:
                    errors.append(f"Event {name} has invalid nominal value {nominal.text!r}")
        for name, expected in EXPECTED_ANIMAL_NOMINALS.items():
            if event_nominals.get(name) != expected:
                errors.append(
                    f"Animal event {name} nominal is {event_nominals.get(name)}, expected {expected}"
                )

    spawn_counts: dict[str, int] = {}
    spawn_root = parsed.get("cfgeventspawns.xml")
    spawn_positions: list[tuple[float, float, str]] = []
    if spawn_root is not None:
        for event in spawn_root.findall("event"):
            name = str(event.attrib.get("name", ""))
            if name not in event_names:
                errors.append(f"Event spawn references undefined event {name}")
            positions = event.findall("pos")
            spawn_counts[name] = len(positions)
            for position in positions:
                try:
                    x = float(position.attrib["x"])
                    z = float(position.attrib["z"])
                except (KeyError, ValueError) as exc:
                    errors.append(f"Invalid event position for {name}: {exc}")
                    continue
                if not (0.0 <= x < WORLD_SIZE and 0.0 <= z < WORLD_SIZE):
                    errors.append(f"Out-of-bounds event position for {name}: {x},{z}")
                    continue
                terrain = height_grid.sample(x, z)
                if name == "VehicleBoat" and terrain > -0.5:
                    errors.append(f"Boat spawn is not in water: {x:.3f},{z:.3f} terrain={terrain:.3f}")
                if name != "VehicleBoat" and terrain < LAND_THRESHOLD:
                    errors.append(f"Land event {name} is in water: {x:.3f},{z:.3f} terrain={terrain:.3f}")
                spawn_positions.append((x, z, name))
        for event_name in VEHICLE_EVENTS:
            if spawn_counts.get(event_name, 0) < 4:
                errors.append(f"Too few {event_name} spawn candidates: {spawn_counts.get(event_name, 0)}")
        for index, (x, z, name) in enumerate(spawn_positions):
            for other_x, other_z, other_name in spawn_positions[index + 1 :]:
                if name == other_name and math.hypot(x - other_x, z - other_z) < 3.0:
                    errors.append(f"Duplicate {name} spawn near {x:.3f},{z:.3f}")
                    break

    prototype = parsed.get("mapgroupproto.xml")
    positions = parsed.get("mapgrouppos.xml")
    group_names: set[str] = set()
    loot_points = 0
    loot_points_by_group: dict[str, int] = {}
    usages_by_group: dict[str, list[str]] = {}
    if prototype is not None:
        definitions = prototype.findall("group")
        names = [str(item.attrib.get("name", "")) for item in definitions]
        group_names = set(names)
        if len(names) != len(group_names):
            errors.append("Duplicate map group definitions")
        for group in definitions:
            group_name = str(group.attrib.get("name", ""))
            group_usages = [str(item.attrib.get("name", "")) for item in group.findall("usage")]
            usages_by_group[group_name] = group_usages
            unknown_usages = sorted(set(group_usages) - VALID_USAGES)
            if unknown_usages:
                errors.append(f"Map group {group_name} has unknown usages: {unknown_usages}")
            points = group.findall("./container/point")
            if not points:
                errors.append(f"Map group {group.attrib.get('name')} has no loot points")
            for point in points:
                try:
                    parse_position(str(point.attrib.get("pos", "")), 3)
                except ValueError as exc:
                    errors.append(f"Invalid loot point in {group.attrib.get('name')}: {exc}")
            loot_points += len(points)
            loot_points_by_group[group_name] = len(points)
        for group_name, expected_usages in EXPECTED_GROUP_USAGES.items():
            actual = set(usages_by_group.get(group_name, []))
            if not expected_usages.issubset(actual):
                errors.append(
                    f"Map group {group_name} usages {sorted(actual)} do not include {sorted(expected_usages)}"
                )

    group_placements = 0
    group_types: dict[str, int] = {}
    if positions is not None:
        group_placements = len(positions.findall("group"))
        counts: dict[str, int] = {}
        seen_ids: set[tuple[str, int, int]] = set()
        for group in positions.findall("group"):
            name = str(group.attrib.get("name", ""))
            counts[name] = counts.get(name, 0) + 1
            if name not in group_names:
                errors.append(f"Map group placement references undefined group {name}")
            try:
                x, y, z = parse_position(str(group.attrib.get("pos", "")), 3)
            except ValueError as exc:
                errors.append(f"Invalid map group position for {name}: {exc}")
                continue
            if not (0.0 <= x < WORLD_SIZE and 0.0 <= z < WORLD_SIZE):
                errors.append(f"Out-of-bounds map group {name}: {x},{z}")
            if height_grid.sample(x, z) < LAND_THRESHOLD:
                errors.append(f"Map group {name} is in water: {x:.3f},{z:.3f}")
            key = (name, round(x * 10), round(z * 10))
            if key in seen_ids:
                errors.append(f"Duplicate map group placement {name} at {x:.3f},{z:.3f}")
            seen_ids.add(key)
            if not math.isfinite(y):
                errors.append(f"Non-finite map group elevation for {name}")
        group_types = counts
        if not (args.minimum_groups <= group_placements <= args.maximum_groups):
            errors.append(
                f"Map group count {group_placements} outside {args.minimum_groups}-{args.maximum_groups}"
            )

    expanded_loot_points = sum(
        count * loot_points_by_group.get(name, 0) for name, count in group_types.items()
    )
    expanded_usage_counts: dict[str, int] = {}
    for group_name, count in group_types.items():
        for usage in usages_by_group.get(group_name, []):
            expanded_usage_counts[usage] = expanded_usage_counts.get(usage, 0) + count

    territory_counts: dict[str, int] = {}
    zombie_root = parsed.get("env/zombie_territories.xml")
    if zombie_root is not None:
        count = 0
        for zone in zombie_root.findall("./territory/zone"):
            count += 1
            name = str(zone.attrib.get("name", ""))
            if name not in event_names:
                errors.append(f"Infected territory references undefined event {name}")
            try:
                x, z = float(zone.attrib["x"]), float(zone.attrib["z"])
            except (KeyError, ValueError) as exc:
                errors.append(f"Invalid infected territory coordinate: {exc}")
                continue
            if height_grid.sample(x, z) < LAND_THRESHOLD:
                errors.append(f"Infected zone {name} is in water: {x:.3f},{z:.3f}")
        territory_counts["zombie_territories.xml"] = count
        if count < 100:
            errors.append(f"Too few infected zones: {count}")

    for relative, root in parsed.items():
        if not relative.startswith("env/") or relative.endswith("zombie_territories.xml"):
            continue
        count = 0
        for territory in root.findall("territory"):
            count += 1
            rest = territory.find("zone[@name='Rest']")
            hunts = territory.findall("zone[@name='HuntingGround']")
            if rest is None or len(hunts) < 1:
                errors.append(f"Incomplete animal territory in {relative}")
                continue
            try:
                x, z = float(rest.attrib["x"]), float(rest.attrib["z"])
            except (KeyError, ValueError) as exc:
                errors.append(f"Invalid animal territory in {relative}: {exc}")
                continue
            if height_grid.sample(x, z) < LAND_THRESHOLD:
                errors.append(f"Animal territory in water in {relative}: {x:.3f},{z:.3f}")
        territory_counts[Path(relative).name] = count

    globals_root = parsed.get("db/globals.xml")
    globals_values = {}
    if globals_root is not None:
        globals_values = {
            str(item.attrib.get("name", "")): str(item.attrib.get("value", ""))
            for item in globals_root.findall("var")
        }
        for name in ("AnimalMaxCount", "InitialSpawn", "SpawnInitial", "ZombieMaxCount", "ZoneSpawnDist"):
            if name not in globals_values:
                errors.append(f"Missing global {name}")

    report = {
        "status": "valid" if not errors else "invalid",
        "ceDirectory": str(root_dir),
        "wrp": str(args.wrp.resolve()),
        "xmlFiles": len(parsed),
        "eventDefinitions": len(event_names),
        "eventNominals": event_nominals,
        "eventSpawns": spawn_counts,
        "mapGroupDefinitions": len(group_names),
        "mapGroupPlacements": group_placements,
        "mapGroupTypeCounts": group_types,
        "placementExpandedUsageCounts": expanded_usage_counts,
        "prototypeLootPoints": loot_points,
        "placementExpandedLootPoints": expanded_loot_points,
        "territories": territory_counts,
        "globals": globals_values,
        "errors": errors,
        "warnings": warnings,
    }
    write_json(args.report.resolve(), report)
    print(f"MICHIGAN_CE_STATUS={report['status']}")
    print(f"MICHIGAN_CE_XML_FILES={len(parsed)}")
    print(f"MICHIGAN_CE_MAP_GROUPS={group_placements}")
    print(f"MICHIGAN_CE_INFECTED_ZONES={territory_counts.get('zombie_territories.xml', 0)}")
    print(f"MICHIGAN_CE_ERRORS={len(errors)}")
    print(f"MICHIGAN_CE_REPORT={args.report.resolve()}")
    if errors:
        for error in errors[:20]:
            print(f"ERROR={error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
