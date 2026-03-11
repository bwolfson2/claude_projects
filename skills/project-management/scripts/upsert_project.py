#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


def parse_value(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def set_path(obj: dict, dotted_key: str, value) -> None:
    parts = dotted_key.split(".")
    cursor = obj
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    cursor[parts[-1]] = value


def append_path(obj: dict, dotted_key: str, value) -> None:
    parts = dotted_key.split(".")
    cursor = obj
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    cursor.setdefault(parts[-1], [])
    if not isinstance(cursor[parts[-1]], list):
        raise TypeError(f"{dotted_key} is not a list")
    cursor[parts[-1]].append(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Upsert fields in projects/projects.json")
    parser.add_argument("--file", default="projects/projects.json")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--append-list", action="append", default=[], metavar="KEY=VALUE")
    args = parser.parse_args()

    path = Path(args.file)
    registry = json.loads(path.read_text(encoding="utf-8"))
    project = next((item for item in registry["projects"] if item["slug"] == args.slug), None)
    if project is None:
        raise SystemExit(f"Project slug not found: {args.slug}")

    for item in args.set:
        key, raw_value = item.split("=", 1)
        set_path(project, key, parse_value(raw_value))

    for item in args.append_list:
        key, raw_value = item.split("=", 1)
        append_path(project, key, parse_value(raw_value))

    registry["last_updated"] = date.today().isoformat()
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
