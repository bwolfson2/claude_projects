#!/usr/bin/env python3
"""
VFT Data Puller — Fetch, normalize, and index structured data.

Saves data from APIs and web scrapes to the project data/ folder
and indexes in the unified messages table.

Usage:
    python pull_data.py --project-slug acme-corp --project-type startup \
        --source-url "https://efts.sec.gov/..." --format json \
        --data '{"filings": [...]}'
    python pull_data.py --from-file /path/to/pull_spec.json
    python pull_data.py --status
"""

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.row_factory = sqlite3.Row
    return conn


def slugify(text: str, max_len: int = 60) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_len]


def _dedup_path(path: Path) -> Path:
    """If path exists, append -2, -3, etc. until unique."""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def save_data_pull(
    conn: sqlite3.Connection,
    project_slug: str,
    project_type: str,
    source_url: str,
    data,
    fmt: str,
    metadata: dict | None = None,
) -> dict:
    """Save fetched data to project data/ folder and index in messages table.

    Args:
        conn: SQLite connection to ingestion.db
        project_slug: e.g. "acme-corp"
        project_type: "startup" or "fund" — determines root folder
        source_url: URL the data was fetched from
        data: The data to save (dict/list for JSON, list-of-dicts for CSV)
        fmt: "json" or "csv"
        metadata: Optional extra metadata dict

    Returns:
        dict with status, file_path, and message_id
    """
    metadata = metadata or {}
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()

    # Determine project root
    if project_type == "fund":
        project_root = REPO_ROOT / "fund"
    else:
        project_root = REPO_ROOT / "companies" / project_slug

    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Build filename from source URL
    url_slug = slugify(source_url.split("//")[-1].split("?")[0])
    if not url_slug:
        url_slug = "pull"

    ext = ".json" if fmt == "json" else ".csv"
    file_path = _dedup_path(data_dir / f"{url_slug}{ext}")

    # Write data file
    if fmt == "json":
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        body_preview = json.dumps(data, default=str)[:500]
        row_count = len(data) if isinstance(data, list) else 1
        columns = list(data[0].keys()) if isinstance(data, list) and data and isinstance(data[0], dict) else []
    elif fmt == "csv":
        if not isinstance(data, list) or not data:
            return {"status": "error", "errors": ["CSV format requires a non-empty list of dicts"]}
        columns = list(data[0].keys())
        row_count = len(data)
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(data)
        body_preview = f"{row_count} rows, columns: {', '.join(columns)}"
    else:
        return {"status": "error", "errors": [f"Unsupported format: {fmt}"]}

    # Build source_id for dedup
    source_id = hashlib.sha256(f"{source_url}{timestamp}".encode()).hexdigest()[:32]

    # Determine type based on how data was obtained
    pull_type = metadata.get("pull_type", "document")  # "document" for API, "scrape" for Chrome

    # Build metadata blob
    meta_blob = {
        "source_url": source_url,
        "format": fmt,
        "row_count": row_count,
        "columns": columns,
        "pull_timestamp": timestamp,
    }
    meta_blob.update(metadata)

    # Insert into messages table
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
                pull_type,
                source_url,
                json.dumps([]),
                f"Data pull: {url_slug}",
                body_preview,
                timestamp,
                None,
                json.dumps([str(file_path)]),
                json.dumps([project_slug]),
                str(file_path),
                json.dumps(meta_blob),
                0,
            ),
        )
        conn.commit()

        if cursor.rowcount == 0:
            return {
                "status": "duplicate",
                "file_path": str(file_path),
            }

        return {
            "status": "saved",
            "file_path": str(file_path),
            "message_id": cursor.lastrowid,
            "row_count": row_count,
        }

    except Exception as e:
        return {"status": "error", "errors": [str(e)]}


class _TableParser(HTMLParser):
    """Simple HTML table parser that extracts rows from <table> elements."""

    def __init__(self):
        super().__init__()
        self.tables = []
        self._current_table = None
        self._current_row = None
        self._current_cell = None
        self._in_cell = False
        self._is_header = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._current_table = {"headers": [], "rows": []}
        elif tag == "tr" and self._current_table is not None:
            self._current_row = []
        elif tag in ("td", "th") and self._current_row is not None:
            self._current_cell = []
            self._in_cell = True
            self._is_header = tag == "th"

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in_cell:
            text = "".join(self._current_cell).strip()
            self._current_row.append(text)
            if self._is_header:
                self._current_table["headers"].append(text)
            self._in_cell = False
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None and self._current_table is not None:
            if self._current_row and not all(
                h in self._current_table["headers"] for h in self._current_row
            ):
                self._current_table["rows"].append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._current_table is not None:
            self.tables.append(self._current_table)
            self._current_table = None

    def handle_data(self, data):
        if self._in_cell and self._current_cell is not None:
            self._current_cell.append(data)


def extract_html_table(html_content: str) -> list[list[dict]]:
    """Parse HTML and extract all tables as lists of dicts.

    Args:
        html_content: Raw HTML string containing <table> elements

    Returns:
        List of tables, each table is a list of dicts (header -> value).
        If no headers found, uses col_0, col_1, etc.
    """
    parser = _TableParser()
    parser.feed(html_content)

    results = []
    for table in parser.tables:
        headers = table["headers"]
        rows = table["rows"]
        if not rows:
            continue

        # If no headers extracted, generate them
        if not headers:
            max_cols = max(len(r) for r in rows)
            headers = [f"col_{i}" for i in range(max_cols)]

        # Normalize header names
        clean_headers = []
        for h in headers:
            clean = re.sub(r"[^a-z0-9]+", "_", h.lower()).strip("_")
            clean_headers.append(clean or f"col_{len(clean_headers)}")

        table_data = []
        for row in rows:
            row_dict = {}
            for i, val in enumerate(row):
                key = clean_headers[i] if i < len(clean_headers) else f"col_{i}"
                row_dict[key] = val
            table_data.append(row_dict)

        results.append(table_data)

    return results


def get_pull_status(limit: int = 20) -> list[dict]:
    """Show recent data pulls from the messages table.

    Returns:
        List of recent data pull records with key fields.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT id, source_id, subject, timestamp, raw_path, metadata
               FROM messages
               WHERE source = 'web' AND type IN ('document', 'scrape')
               ORDER BY timestamp DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

        results = []
        for row in rows:
            meta = json.loads(row["metadata"]) if row["metadata"] else {}
            results.append({
                "id": row["id"],
                "subject": row["subject"],
                "timestamp": row["timestamp"],
                "raw_path": row["raw_path"],
                "source_url": meta.get("source_url"),
                "format": meta.get("format"),
                "row_count": meta.get("row_count"),
            })

        conn.close()
        return results

    except Exception as e:
        conn.close()
        return [{"error": str(e)}]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Data Puller")
    parser.add_argument("--project-slug", type=str, help="Project slug (e.g. acme-corp)")
    parser.add_argument("--project-type", type=str, default="startup",
                        help="Project type: startup or fund")
    parser.add_argument("--source-url", type=str, help="URL the data was fetched from")
    parser.add_argument("--format", type=str, dest="fmt", default="json",
                        help="Output format: json or csv")
    parser.add_argument("--data", type=str, help="Data as JSON string")
    parser.add_argument("--from-file", type=str, help="Load pull spec from JSON file")
    parser.add_argument("--status", action="store_true", help="Show recent data pulls")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.status:
        pulls = get_pull_status()
        print(json.dumps(pulls, indent=2))
        sys.exit(0)

    if args.from_file:
        with open(args.from_file) as f:
            spec = json.load(f)
        project_slug = spec["project_slug"]
        project_type = spec.get("project_type", "startup")
        source_url = spec["source_url"]
        data = spec["data"]
        fmt = spec.get("format", "json")
        metadata = spec.get("metadata", {})
    elif args.data:
        project_slug = args.project_slug
        project_type = args.project_type
        source_url = args.source_url
        data = json.loads(args.data)
        fmt = args.fmt
        metadata = {}
    else:
        print("Error: provide --data or --from-file", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(json.dumps({
            "status": "dry_run",
            "project_slug": project_slug,
            "source_url": source_url,
            "format": fmt,
            "data_preview": json.dumps(data, default=str)[:200],
        }, indent=2))
        sys.exit(0)

    conn = get_db()
    result = save_data_pull(conn, project_slug, project_type, source_url, data, fmt, metadata)
    conn.close()
    print(json.dumps(result, indent=2))
