#!/usr/bin/env python3
"""
VFT Transcript Ingestion — Granola MCP Integration

This script provides helpers for ingesting meeting transcripts from the
Granola MCP connector. Claude reads this script and uses the Granola MCP
tools (list_meetings, get_meeting_transcript, query_granola) to pull
transcripts, then calls the helper functions to save and index them.

Usage (by Claude):
    Read this script, then use Granola MCP tools to fetch meetings.
    Call save_transcript() for each new meeting.

Standalone helpers:
    python ingest_transcripts.py --status          # Show ingestion status
    python ingest_transcripts.py --since 2026-03-01 # Show what would be ingested
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"
TRANSCRIPTS_ROOT = REPO_ROOT / "fund" / "transcripts"
DEALS_PATH = REPO_ROOT / "fund" / "crm" / "deals.json"


def get_db() -> sqlite3.Connection:
    """Get a connection to the ingestion database."""
    if not DB_PATH.exists():
        print(f"[VFT] Database not found at {DB_PATH}. Run init_db.py first.")
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.row_factory = sqlite3.Row
    return conn


def slugify(text: str, max_len: int = 60) -> str:
    """Convert text to a URL-friendly slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:max_len]


def is_already_ingested(conn: sqlite3.Connection, granola_id: str) -> bool:
    """Check if a transcript has already been ingested."""
    row = conn.execute(
        "SELECT id FROM transcripts WHERE granola_id = ?", (granola_id,)
    ).fetchone()
    return row is not None


def extract_participant_emails(participants: list) -> list:
    """Extract email addresses from participant strings.

    Handles formats like:
    - "John Doe (john@example.com)"
    - "john@example.com"
    - "John Doe <john@example.com>"
    """
    emails = []
    email_pattern = r'[\w.+-]+@[\w-]+\.[\w.-]+'

    for p in participants:
        found = re.findall(email_pattern, str(p))
        emails.extend(found)

    return emails


def save_transcript(
    conn: sqlite3.Connection,
    granola_id: str,
    title: str,
    participants: list,
    date: str,
    summary: str = "",
    transcript_text: str = "",
    action_items: list = None,
    duration: str = "",
) -> dict:
    """
    Save a transcript to the filesystem and index in the database.
    Returns a dict with the saved path and database id.
    """
    if is_already_ingested(conn, granola_id):
        return {"status": "skipped", "reason": "already_ingested", "granola_id": granola_id}

    # Determine folder
    try:
        dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        dt = datetime.now()

    month_folder = dt.strftime("%Y-%m")
    date_suffix = dt.strftime("%m%d")
    meeting_slug = f"{slugify(title)}-{date_suffix}"

    # Ensure unique path
    file_path = TRANSCRIPTS_ROOT / month_folder / f"{meeting_slug}.md"
    counter = 2
    base_path = file_path
    while file_path.exists():
        file_path = base_path.parent / f"{base_path.stem}-{counter}{base_path.suffix}"
        counter += 1

    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Build markdown content
    participants_str = ", ".join(participants) if participants else "Unknown"
    action_items_str = ""
    if action_items:
        action_items_str = "\n## Action Items\n\n" + "\n".join(
            f"- {item}" for item in action_items
        )

    content = f"""# {title}

**Date:** {date}
**Participants:** {participants_str}
**Duration:** {duration or 'N/A'}
**Granola ID:** {granola_id}

## Summary

{summary or 'No summary available.'}
{action_items_str}

## Transcript

{transcript_text or 'No transcript text available.'}

---
*Ingested from Granola on {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
    file_path.write_text(content, encoding="utf-8")

    # Insert into DB
    conn.execute(
        """INSERT INTO transcripts
           (granola_id, title, participants, date, summary, raw_path)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            granola_id,
            title,
            participants_str,
            date,
            (summary or transcript_text)[:500],
            str(file_path),
        ),
    )

    transcript_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Also write to unified messages table (v2)
    participant_emails = extract_participant_emails(participants)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO messages
               (source, source_id, type, sender, recipients, subject, body,
                timestamp, channel, attachments, project_tags, raw_path,
                metadata, classified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "granola",
                granola_id,
                "transcript",
                None,
                json.dumps(participants if participants else []),
                title,
                (summary or transcript_text)[:500],
                date,
                "meeting",
                "[]",
                "[]",
                str(file_path),
                json.dumps({"legacy_transcript_id": transcript_id, "duration": duration, "participant_emails": participant_emails}),
                0,
            ),
        )
    except Exception:
        pass  # Unified table may not exist in older schema — graceful degradation

    conn.commit()

    return {
        "status": "saved",
        "id": transcript_id,
        "file_path": str(file_path),
        "granola_id": granola_id,
    }


def get_ingestion_status(conn: sqlite3.Connection) -> dict:
    """Get current ingestion statistics."""
    total = conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
    unclassified = conn.execute(
        "SELECT COUNT(*) FROM transcripts WHERE classified = 0"
    ).fetchone()[0]
    latest = conn.execute(
        "SELECT date FROM transcripts ORDER BY date DESC LIMIT 1"
    ).fetchone()

    return {
        "total_transcripts": total,
        "unclassified": unclassified,
        "latest_transcript_date": latest[0] if latest else "none",
    }


def get_last_ingestion_date(conn: sqlite3.Connection) -> str:
    """Get the date of the most recently ingested transcript."""
    row = conn.execute(
        "SELECT MAX(date) FROM transcripts"
    ).fetchone()
    return row[0] if row and row[0] else ""


# ── WORKFLOW (for Claude to follow) ──────────────────────────────────────
"""
GRANOLA MCP WORKFLOW:

1. CHECK LAST INGESTION
   - Call get_last_ingestion_date() to know where to start
   - If no previous ingestion, use --since date or default to last 7 days

2. LIST MEETINGS
   - Use the Granola MCP tool: list_meetings or get_meetings
   - Filter to meetings since the last ingestion date
   - Collect meeting IDs, titles, dates, participants

3. FOR EACH NEW MEETING:
   a. Check is_already_ingested(conn, granola_id)
   b. If not ingested:
      - Use get_meeting_transcript(meeting_id) to fetch full transcript
      - Extract: title, participants, date, summary, transcript text, action items
      - Call save_transcript() with all extracted data

4. FINISH
   - Print ingestion summary
   - Trigger deal-project-classifier if new transcripts were saved
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Transcript Ingestion helpers")
    parser.add_argument("--status", action="store_true", help="Show ingestion status")
    parser.add_argument("--since", type=str, help="Only show meetings after this date")
    parser.add_argument("--max-meetings", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = get_db()

    if args.status:
        status = get_ingestion_status(conn)
        last = get_last_ingestion_date(conn)
        print(f"[VFT Transcript Ingestion Status]")
        print(f"  Total transcripts indexed: {status['total_transcripts']}")
        print(f"  Unclassified: {status['unclassified']}")
        print(f"  Latest transcript: {status['latest_transcript_date']}")
        print(f"  Last ingestion date: {last or 'never'}")
    else:
        since = args.since or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"[VFT] Transcript ingestion ready.")
        print(f"  Since: {since} | Max: {args.max_meetings} meetings")
        print(f"  Transcripts root: {TRANSCRIPTS_ROOT}")
        print(f"  Database: {DB_PATH}")
        status = get_ingestion_status(conn)
        print(f"  Transcripts indexed so far: {status['total_transcripts']}")

    conn.close()
