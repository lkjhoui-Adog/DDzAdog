#!/usr/bin/env python3
"""Delete a CfgWorlds Navmesh class for terrain-only DayZ tests."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def find_matching_brace(text: str, open_brace: int) -> int:
    depth = 0
    index = open_brace
    state = "code"

    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""

        if state == "line_comment":
            if char == "\n":
                state = "code"
        elif state == "block_comment":
            if char == "*" and next_char == "/":
                state = "code"
                index += 1
        elif state == "string":
            if char == "\\":
                index += 1
            elif char == '"':
                state = "code"
        else:
            if char == "/" and next_char == "/":
                state = "line_comment"
                index += 1
            elif char == "/" and next_char == "*":
                state = "block_comment"
                index += 1
            elif char == '"':
                state = "string"
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index

        index += 1

    raise ValueError("Navmesh class has no matching closing brace")


def disable_navmesh(text: str) -> str:
    match = re.search(r"(?m)^[ \t]*class[ \t]+Navmesh\b", text)
    if not match:
        raise ValueError("No class Navmesh declaration found")

    open_brace = text.find("{", match.end())
    if open_brace < 0:
        raise ValueError("Navmesh class has no opening brace")

    close_brace = find_matching_brace(text, open_brace)
    end = close_brace + 1
    while end < len(text) and text[end] in " \t\r\n":
        end += 1
    if end < len(text) and text[end] == ";":
        end += 1
    while end < len(text) and text[end] in " \t":
        end += 1
    if end < len(text) and text[end] == "\r":
        end += 1
    if end < len(text) and text[end] == "\n":
        end += 1

    # CAWorld already supplies a Navmesh child class. Removing only the local
    # override exposes that inherited class, so the config must explicitly
    # delete it to prevent the engine from resolving a missing mesh path.
    marker = "        delete Navmesh; // Disabled for this road-only terrain test.\n"
    return text[: match.start()] + marker + text[end:]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    source = args.config.resolve()
    output = args.output.resolve() if args.output else source
    result = disable_navmesh(source.read_text(encoding="utf-8-sig"))
    output.write_text(result, encoding="utf-8", newline="\n")
    print(f"Navmesh class removed: {source} -> {output}")


if __name__ == "__main__":
    main()
