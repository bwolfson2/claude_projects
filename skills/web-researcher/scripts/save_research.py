#!/usr/bin/env python3
"""
VFT Web Researcher — Research Item Saver

Saves web research results to the project's research/ folder and indexes
them in the unified messages table as source="web", type="scrape".

Usage:
    python save_research.py --project acme-corp --project-type dd \
        --url "https://example.com" --title "Acme Corp Website" \
        --content-file /path/to/extracted.md

    python save_research.py --status --project acme-corp
"""

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"

# Project type to base directory mapping
PROJECT_DIRS = {
    "dd": REPO_ROOT / "fund" / "projects",
    "hiring": REPO_ROOT / "hiring" / "projects",
    "research": REPO_ROOT / "research" / "projects",
}


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.row_factory = sqlite3.Row
    return conn


def slugify(text: str, max_len: int = 60) -> str:
    """Convert text to a URL/filename-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"https?://", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug[:max_len]


def url_hash(url: str) -> str:
    """Generate a stable short hash from a URL for use as source_id."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def resolve_project_dir(project_slug: str, project_type: str) -> Path:
    """Resolve the project directory based on type."""
    base = PROJECT_DIRS.get(project_type)
    if base is None:
        # Fallback: search all known bases
        for d in PROJECT_DIRS.values():
            candidate = d / project_slug
            if candidate.exists():
                return candidate
        # Default to dd
        base = PROJECT_DIRS["dd"]
    return base / project_slug


def save_research_item(
    conn: sqlite3.Connection,
    project_slug: str,
    project_type: str,
    source_url: str,
    title: str,
    content: str,
    metadata: dict | None = None,
) -> dict:
    """Save a research item to disk and index in the messages table.

    1. Writes markdown file to {project_dir}/research/{slug}.md
    2. Inserts into unified messages table with source="web", type="scrape"
    3. Dedup on (source, source_id) where source_id = URL hash

    Returns dict with status, file_path, and message_id.
    """
    metadata = metadata or {}
    now = datetime.now(timezone.utc)
    source_id = url_hash(source_url)
    file_slug = slugify(title) or slugify(source_url)

    # Resolve project directory and ensure research/ exists
    project_dir = resolve_project_dir(project_slug, project_type)
    research_dir = project_dir / "research"
    research_dir.mkdir(parents=True, exist_ok=True)

    # Write markdown file
    file_path = research_dir / f"{file_slug}.md"
    # Handle duplicates in filesystem
    counter = 2
    while file_path.exists():
        file_path = research_dir / f"{file_slug}-{counter}.md"
        counter += 1

    file_path.write_text(content, encoding="utf-8")

    # Ensure messages table exists
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    if "messages" not in tables:
        print("[VFT] Messages table not found. Run migrate_v2_unified_messages.py first.")
        return {"status": "error", "errors": ["messages table not found -- run migration"]}

    # Build enriched metadata
    enriched_meta = {
        "source_url": source_url,
        "extraction_date": now.isoformat(),
        "project_type": project_type,
        **metadata,
    }

    # Insert into unified messages table
    try:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO messages
               (source, source_id, type, sender, recipients, subject, body,
                timestamp, channel, attachments, project_tags, raw_path,
                metadata, classified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "web",
                source_id,
                "scrape",
                None,
                json.dumps([]),
                title,
                content[:5000],  # Store preview in body, full content on disk
                now.isoformat(),
                source_url,
                json.dumps([]),
                json.dumps([project_slug]),
                str(file_path),
                json.dumps(enriched_meta),
                0,
            ),
        )
        conn.commit()

        if cursor.rowcount == 0:
            existing = conn.execute(
                "SELECT id FROM messages WHERE source = ? AND source_id = ?",
                ("web", source_id),
            ).fetchone()
            return {
                "status": "duplicate",
                "file_path": str(file_path),
                "message_id": existing["id"] if existing else None,
            }

        return {
            "status": "inserted",
            "file_path": str(file_path),
            "message_id": cursor.lastrowid,
        }

    except Exception as e:
        return {"status": "error", "file_path": str(file_path), "errors": [str(e)]}


def get_research_status(project_slug: str) -> dict:
    """Check what research has been gathered for a project.

    Returns dict with counts and list of scraped sources.
    """
    conn = get_db()

    # Query messages table for web scrapes tagged to this project
    try:
        rows = conn.execute(
            """SELECT source_id, subject, channel, timestamp, metadata
               FROM messages
               WHERE source = 'web' AND type = 'scrape'
               AND project_tags LIKE ?""",
            (f'%"{project_slug}"%',),
        ).fetchall()
    except Exception:
        conn.close()
        return {"status": "error", "total": 0, "sources": []}

    sources = []
    for row in rows:
        meta = json.loads(row["metadata"]) if row["metadata"] else {}
        sources.append(
            {
                "source_id": row["source_id"],
                "title": row["subject"],
                "url": row["channel"],
                "scraped_at": row["timestamp"],
                "extraction_date": meta.get("extraction_date"),
            }
        )

    conn.close()
    return {
        "status": "ok",
        "project": project_slug,
        "total": len(sources),
        "sources": sources,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Web Research Saver")
    parser.add_argument("--project", type=str, required=True, help="Project slug")
    parser.add_argument(
        "--project-type",
        type=str,
        default="dd",
        choices=["dd", "hiring", "research"],
        help="Project type (default: dd)",
    )
    parser.add_argument("--url", type=str, help="Source URL")
    parser.add_argument("--title", type=str, help="Research item title")
    parser.add_argument("--content-file", type=str, help="Path to extracted content markdown")
    parser.add_argument("--content", type=str, help="Content as inline string")
    parser.add_argument("--metadata", type=str, help="Extra metadata as JSON string")
    parser.add_argument("--status", action="store_true", help="Show research status for project")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    if args.status:
        result = get_research_status(args.project)
        print(json.dumps(result, indent=2))
        sys.exit(0)

    # Validate required args for save
    if not args.url or not args.title:
        print("Error: --url and --title are required for saving research items.")
        sys.exit(1)

    # Get content
    if args.content_file:
        content = Path(args.content_file).read_text(encoding="utf-8")
    elif args.content:
        content = args.content
    else:
        # Read from stdin
        if not sys.stdin.isatty():
            content = sys.stdin.read()
        else:
            print("Error: Provide content via --content-file, --content, or stdin.")
            sys.exit(1)

    metadata = json.loads(args.metadata) if args.metadata else {}

    if args.dry_run:
        print(json.dumps({
            "status": "dry_run",
            "project": args.project,
            "project_type": args.project_type,
            "url": args.url,
            "title": args.title,
            "content_length": len(content),
            "metadata": metadata,
        }, indent=2))
        sys.exit(0)

    conn = get_db()
    result = save_research_item(
        conn=conn,
        project_slug=args.project,
        project_type=args.project_type,
        source_url=args.url,
        title=args.title,
        content=content,
        metadata=metadata,
    )
    conn.close()
    print(json.dumps(result, indent=2))
