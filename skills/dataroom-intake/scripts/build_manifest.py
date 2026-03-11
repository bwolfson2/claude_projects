#!/usr/bin/env python3
"""Build a lightweight manifest for a startup dataroom."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path


CATEGORY_KEYWORDS = {
    "commercial": ["customer", "pipeline", "sales", "marketing", "gtm", "market", "revenue"],
    "finance": ["finance", "financial", "budget", "forecast", "burn", "runway", "arr", "mrr"],
    "legal": ["legal", "contract", "msa", "sow", "privacy", "gdpr", "ip", "patent", "nda"],
    "product_technical": ["product", "roadmap", "architecture", "security", "engineering", "tech", "api"],
    "governance": ["board", "cap table", "captable", "safe", "note", "equity", "option"],
}

EXTENSION_HINTS = {
    ".csv": "data_export",
    ".doc": "document",
    ".docx": "document",
    ".jpg": "image",
    ".jpeg": "image",
    ".md": "text",
    ".pdf": "pdf",
    ".png": "image",
    ".ppt": "presentation",
    ".pptx": "presentation",
    ".txt": "text",
    ".xls": "spreadsheet",
    ".xlsx": "spreadsheet",
    ".zip": "archive",
}


def infer_category(path: Path) -> str:
    haystack = str(path).lower()
    scores = Counter()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in haystack:
                scores[category] += 1
    if scores:
        return scores.most_common(1)[0][0]
    return "uncategorized"


def build_manifest(root: Path) -> dict:
    files = []
    category_counts = Counter()
    kind_counts = Counter()

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        extension = path.suffix.lower()
        category = infer_category(path.relative_to(root))
        kind = EXTENSION_HINTS.get(extension, "other")
        category_counts[category] += 1
        kind_counts[kind] += 1
        files.append(
            {
                "path": str(path.relative_to(root)),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                "extension": extension or "<none>",
                "kind": kind,
                "category": category,
            }
        )

    return {
        "root": str(root),
        "generated_at": datetime.now(UTC).isoformat(),
        "file_count": len(files),
        "category_counts": dict(category_counts),
        "kind_counts": dict(kind_counts),
        "files": files,
    }


def write_markdown(manifest: dict, output_path: Path) -> None:
    lines = [
        "# Dataroom Manifest",
        "",
        f"- Root: `{manifest['root']}`",
        f"- Generated: `{manifest['generated_at']}`",
        f"- File count: `{manifest['file_count']}`",
        "",
        "## Category Counts",
        "",
    ]

    for category, count in sorted(manifest["category_counts"].items()):
        lines.append(f"- {category}: {count}")

    lines.extend(["", "## File Types", ""])

    for kind, count in sorted(manifest["kind_counts"].items()):
        lines.append(f"- {kind}: {count}")

    lines.extend(["", "## Files", ""])

    for item in manifest["files"]:
        lines.append(
            f"- `{item['path']}` | {item['category']} | {item['kind']} | {item['size_bytes']} bytes"
        )

    output_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a dataroom manifest.")
    parser.add_argument("root", help="Path to the dataroom root folder")
    parser.add_argument("--json-out", help="Optional path for JSON output")
    parser.add_argument("--md-out", help="Optional path for Markdown output")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    manifest = build_manifest(root)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(manifest, indent=2) + "\n")
    else:
        print(json.dumps(manifest, indent=2))

    if args.md_out:
        write_markdown(manifest, Path(args.md_out))


if __name__ == "__main__":
    main()
