#!/usr/bin/env python3
"""
VFT Document Processor — Dataroom Batch Text Extraction

Extracts text from all files in a dataroom and populates document_pages.
RLM structured extraction is done by Claude Code driving process_document.py
subcommands with its own reasoning — no API calls from this script.

Usage:
    python process_dataroom.py --path /path/to/dataroom --slug midbound_dataroom
    python process_dataroom.py --path /path/to/dataroom --slug midbound_dataroom --dry-run
    python process_dataroom.py --manifest /path/to/manifest.json --slug midbound_dataroom
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, UTC
from pathlib import Path

REPO_ROOT = Path(os.environ.get("VFT_REPO_ROOT",
    Path(__file__).resolve().parents[3]))
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"

sys.path.insert(0, str(Path(__file__).parent))
from extract_text import extract_directory, get_db


def load_or_build_manifest(dataroom_path: Path, manifest_path: Path = None) -> dict:
    """Load existing manifest or build one from the dataroom."""
    if manifest_path and manifest_path.exists():
        with open(manifest_path) as f:
            return json.load(f)

    # Import build_manifest from dataroom-intake
    intake_scripts = REPO_ROOT / "skills" / "dataroom-intake" / "scripts"
    sys.path.insert(0, str(intake_scripts))
    try:
        from build_manifest import build_manifest
        return build_manifest(dataroom_path)
    except ImportError:
        print("[VFT] build_manifest.py not found. Building minimal manifest.", file=sys.stderr)
        files = []
        for p in sorted(dataroom_path.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                files.append({
                    "path": str(p.relative_to(dataroom_path)),
                    "category": "uncategorized",
                    "kind": p.suffix.lower().lstrip(".") or "other",
                    "size_bytes": p.stat().st_size,
                })
        return {"root": str(dataroom_path), "files": files, "file_count": len(files)}


def create_job(conn: sqlite3.Connection, dataroom_slug: str, job_type: str, file_path: str = None) -> int:
    """Create or get a processing job record."""
    existing = conn.execute(
        """SELECT id, status FROM document_jobs
           WHERE dataroom_slug = ? AND file_path IS ? AND job_type = ?""",
        (dataroom_slug, file_path, job_type),
    ).fetchone()

    if existing:
        if existing["status"] == "complete":
            return None
        return existing["id"]

    cursor = conn.execute(
        """INSERT OR IGNORE INTO document_jobs (dataroom_slug, file_path, job_type, status, started_at)
           VALUES (?, ?, ?, 'running', datetime('now'))""",
        (dataroom_slug, file_path, job_type),
    )
    conn.commit()
    return cursor.lastrowid


def update_job(conn: sqlite3.Connection, job_id: int, **kwargs):
    """Update job fields."""
    if job_id is None:
        return
    sets = []
    values = []
    for key, val in kwargs.items():
        sets.append(f"{key} = ?")
        values.append(val)
    values.append(job_id)
    conn.execute(f"UPDATE document_jobs SET {', '.join(sets)} WHERE id = ?", values)
    conn.commit()


def process_dataroom(
    dataroom_path: Path,
    dataroom_slug: str,
    manifest_path: Path = None,
    dry_run: bool = False,
) -> dict:
    """Extract text from all files in a dataroom.

    Returns summary dict with extraction stats.
    RLM structured extraction is handled separately by Claude Code
    driving process_document.py subcommands.
    """
    conn = get_db()
    manifest = load_or_build_manifest(dataroom_path, manifest_path)

    summary = {
        "dataroom": dataroom_slug,
        "path": str(dataroom_path),
        "total_files": manifest["file_count"],
        "extraction": {"extracted": 0, "skipped": 0, "unsupported": 0, "errors": 0, "total_pages": 0},
        "dry_run": dry_run,
    }

    print(f"\n[VFT] Text extraction for {dataroom_slug}")
    print(f"[VFT] {manifest['file_count']} files in dataroom")

    if dry_run:
        from extract_text import EXTRACTORS
        for f in manifest["files"]:
            ext = Path(f["path"]).suffix.lower()
            if ext in EXTRACTORS:
                summary["extraction"]["extracted"] += 1
            else:
                summary["extraction"]["unsupported"] += 1
        print(f"[VFT] Dry run: {summary['extraction']['extracted']} files would be extracted")
        conn.close()
        return summary

    job_id = create_job(conn, dataroom_slug, "batch")

    extraction_result = extract_directory(dataroom_path, dataroom_slug, conn)
    summary["extraction"] = {
        "extracted": extraction_result["extracted"],
        "skipped": extraction_result["skipped"],
        "unsupported": extraction_result["unsupported"],
        "errors": extraction_result["errors"],
        "total_pages": extraction_result["total_pages"],
    }
    print(f"[VFT] Extracted: {extraction_result['extracted']} files, {extraction_result['total_pages']} pages")

    if job_id:
        update_job(conn, job_id, status="complete",
                   total_pages=extraction_result["total_pages"],
                   completed_at=datetime.now(UTC).isoformat())

    conn.close()
    print(f"\n[VFT] Text extraction complete.")
    print(f"[VFT] Use process_document.py subcommands for RLM structured extraction.")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Dataroom Batch Text Extraction")
    parser.add_argument("--path", required=True, help="Path to dataroom directory")
    parser.add_argument("--slug", required=True, help="Dataroom slug identifier")
    parser.add_argument("--manifest", help="Path to existing manifest.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db", type=str, help="Path to ingestion.db")
    args = parser.parse_args()

    if args.db:
        import extract_text
        extract_text.DB_PATH = Path(args.db)

    dataroom_path = Path(args.path).expanduser().resolve()
    if not dataroom_path.is_dir():
        print(f"[VFT] Not a directory: {dataroom_path}", file=sys.stderr)
        sys.exit(1)

    manifest_path = Path(args.manifest) if args.manifest else None

    result = process_dataroom(
        dataroom_path=dataroom_path,
        dataroom_slug=args.slug,
        manifest_path=manifest_path,
        dry_run=args.dry_run,
    )

    print(json.dumps(result, indent=2))
