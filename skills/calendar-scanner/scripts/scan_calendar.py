#!/usr/bin/env python3
"""
VFT Calendar Scanner — Google Calendar / Outlook Calendar Orchestration

This script is designed to be executed by Claude (not run standalone).
It provides the logic and state management for scanning calendar events
via Google Calendar MCP, Microsoft 365 MCP, or Claude in Chrome.
Claude reads this script, follows the workflow, and uses the appropriate
tools to interact with the calendar.

Usage (by Claude):
    Read this script, then follow the WORKFLOW section using MCP or Chrome tools.
    Call the helper functions via python to manage state and persistence.

Standalone helpers:
    python scan_calendar.py --status         # Show scan status
    python scan_calendar.py --init-db        # Ensure DB schema exists
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
REPO_ROOT = Path(__file__).resolve().parents[3]  # skills/calendar-scanner/scripts → repo root
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"
INBOX_ROOT = REPO_ROOT / "fund" / "inbox" / "calendar"
CONFIG_PATH = REPO_ROOT / "fund" / "metadata" / "config.json"

# ── Constants ────────────────────────────────────────────────────────────
SOURCE = "calendar"
EVENT_TYPE = "event"


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


def make_source_id(calendar_id: str, event_id: str) -> str:
    """Generate a dedup key from calendar event identifiers."""
    return f"{calendar_id}|{event_id}"


def is_already_scanned(conn: sqlite3.Connection, source_id: str) -> bool:
    """Check if an event has already been ingested."""
    row = conn.execute(
        "SELECT id FROM messages WHERE source = ? AND source_id = ?",
        (SOURCE, source_id),
    ).fetchone()
    return row is not None


def extract_attendee_domains(attendees: list) -> list:
    """Extract unique domains from attendee email addresses.

    Args:
        attendees: List of dicts with 'email' key, or list of email strings.

    Returns:
        Sorted list of unique domains (excluding common personal email providers).
    """
    domains = set()
    personal_domains = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
                        "icloud.com", "me.com", "aol.com", "protonmail.com",
                        "proton.me", "live.com"}
    for attendee in attendees:
        email = attendee.get("email", attendee) if isinstance(attendee, dict) else str(attendee)
        if "@" in email:
            domain = email.split("@")[-1].lower().strip()
            if domain and domain not in personal_domains:
                domains.add(domain)
    return sorted(domains)


def save_event(
    conn: sqlite3.Connection,
    title: str,
    organizer: str,
    attendees: list,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    calendar_name: str = "primary",
    calendar_id: str = "primary",
    event_id: str = "",
    conference_url: str = "",
    status: str = "confirmed",
) -> dict:
    """
    Save a calendar event to the filesystem and index in the database.
    Returns a dict with the saved paths and database id.

    Args:
        conn: Database connection
        title: Event title/summary
        organizer: Organizer name and/or email
        attendees: List of dicts with name, email, status keys
        start: ISO-8601 start time
        end: ISO-8601 end time
        description: Event description/body text
        location: Physical location or video meeting link
        calendar_name: Display name of the calendar
        calendar_id: Calendar identifier (e.g., "primary", email address)
        event_id: Unique event identifier from the calendar provider
        conference_url: Video conference URL if present
        status: Event status (confirmed, tentative, cancelled)
    """
    source_id = make_source_id(calendar_id, event_id)

    if is_already_scanned(conn, source_id):
        return {"status": "skipped", "reason": "already_scanned", "source_id": source_id}

    # Determine folder and file path
    try:
        dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        dt = datetime.now()

    month_folder = dt.strftime("%Y-%m")
    date_str = dt.strftime("%Y-%m-%d")
    start_time = dt.strftime("%H:%M")

    try:
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        end_time = end_dt.strftime("%H:%M")
    except (ValueError, AttributeError):
        end_time = ""

    time_range = f"{start_time}--{end_time}" if end_time else start_time

    # Build folder path
    folder = INBOX_ROOT / month_folder
    folder.mkdir(parents=True, exist_ok=True)

    # Build event file path (one file per day, append events)
    event_file = folder / f"events-{date_str}.md"

    # Format attendee list
    attendee_names = []
    for a in attendees:
        if isinstance(a, dict):
            name = a.get("name", a.get("email", "Unknown"))
            attendee_names.append(name)
        else:
            attendee_names.append(str(a))
    attendee_str = ", ".join(attendee_names) if attendee_names else "None"

    # Build event block
    event_block = f"""
### {title} -- {time_range}
**Organizer:** {organizer}
**Attendees:** {attendee_str}
**Location:** {location or "Not specified"}
**Status:** {status}

{description}

---
"""

    # Write or append to file
    if event_file.exists():
        with open(event_file, "a", encoding="utf-8") as f:
            f.write(event_block)
    else:
        header = f"# Calendar Events -- {date_str}\n"
        event_file.write_text(header + event_block, encoding="utf-8")

    abs_path = str(event_file)

    # Extract attendee domains for classification
    attendee_domains = extract_attendee_domains(attendees)

    # Build body for DB (description + attendee info)
    body_parts = []
    if description:
        body_parts.append(description[:2000])
    if attendee_names:
        body_parts.append(f"Attendees: {attendee_str}")
    if location:
        body_parts.append(f"Location: {location}")
    full_body = "\n".join(body_parts)

    # Build metadata JSON
    metadata = json.dumps({
        "calendar_id": calendar_id,
        "event_id": event_id,
        "start": start,
        "end": end,
        "location": location,
        "conference_url": conference_url,
        "attendees": attendees,
        "recurrence": None,
        "status": status,
        "attendee_domains": attendee_domains,
    })

    # Build recipients from attendee emails
    recipient_emails = []
    for a in attendees:
        if isinstance(a, dict) and a.get("email"):
            recipient_emails.append(a["email"])

    # Insert into unified messages table (with retry on lock)
    insert_sql = """INSERT OR IGNORE INTO messages
       (source, source_id, type, sender, recipients, subject, body,
        timestamp, channel, attachments, project_tags, raw_path,
        metadata, classified)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
    insert_params = (
        SOURCE,
        source_id,
        EVENT_TYPE,
        organizer,
        json.dumps(recipient_emails),
        title,
        full_body[:5000] if full_body else "",
        start,
        calendar_name,
        "[]",
        json.dumps([]),
        abs_path,
        metadata,
        0,
    )

    try:
        conn.execute(insert_sql, insert_params)
    except Exception as e:
        import time
        for attempt in range(3):
            try:
                time.sleep(2)
                conn.execute(insert_sql, insert_params)
                break
            except Exception:
                if attempt == 2:
                    return {"status": "error", "reason": str(e), "source_id": source_id}

    conn.commit()

    message_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    return {
        "status": "saved",
        "id": message_id,
        "folder": str(folder),
        "file": str(event_file),
        "source_id": source_id,
        "attendee_domains": attendee_domains,
    }


def get_scan_status(conn: sqlite3.Connection) -> dict:
    """Get current scan statistics for calendar events."""
    total = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE source = ?", (SOURCE,)
    ).fetchone()[0]
    unclassified = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE source = ? AND classified = 0", (SOURCE,)
    ).fetchone()[0]
    latest = conn.execute(
        "SELECT timestamp FROM messages WHERE source = ? ORDER BY timestamp DESC LIMIT 1",
        (SOURCE,),
    ).fetchone()
    calendars = conn.execute(
        "SELECT DISTINCT channel FROM messages WHERE source = ?", (SOURCE,)
    ).fetchall()

    return {
        "total_events": total,
        "unclassified": unclassified,
        "latest_event_ts": latest[0] if latest else "none",
        "calendars_scanned": [r[0] for r in calendars],
    }


def get_calendar_provider() -> str:
    """Read preferred calendar provider from config.json if available."""
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text())
            cal_config = config.get("channels", {}).get("calendar", {})
            return cal_config.get("provider", "all")
        except (json.JSONDecodeError, KeyError):
            pass
    return "all"


# ── WORKFLOW (for Claude to follow) ──────────────────────────────────────
"""
CLAUDE CALENDAR SCANNING WORKFLOW:

1. CHECK CONNECTOR
   - Search for Google Calendar MCP connector using mcp-registry search
   - If available and connected, prefer Google Calendar MCP tools
   - If not, search for Microsoft 365 MCP connector (ms365)
   - If ms365 available, use it for Outlook Calendar access
   - If neither available, use Claude in Chrome browser automation (steps below)
   - Call get_calendar_provider() to check user's preferred provider from config

2. LIST EVENTS (via MCP connector)
   - Use the calendar connector to list events for the configured window:
     - Past: yesterday (--past-days 1)
     - Future: next 7 days (--lookback-days 7)
   - Filter to the user's primary calendar (or all calendars)
   - Get event details: title, start, end, organizer, attendees, location, description

   LIST EVENTS (via Chrome fallback)
   - Navigate to https://calendar.google.com/ (or https://outlook.cloud.microsoft/calendar/)
   - Switch to Schedule/List view for easier extraction
   - Use read_page to get the accessibility tree of visible events
   - Click each event to open the detail popup
   - Use get_page_text to extract full event details
   - Navigate through date range using arrows or date picker

3. FOR EACH EVENT:
   - Build source_id: make_source_id(calendar_id, event_id)
   - Call is_already_scanned() to check for duplicates
   - If new, call save_event() with all extracted metadata
   - save_event() handles:
     a. Writing/appending to events-{date}.md
     b. Inserting into the unified messages table
     c. Extracting attendee domains for deal matching

4. ATTENDEE DOMAIN MATCHING
   - For each event with external attendees (non-personal email domains):
     - The attendee_domains list is stored in metadata
     - The deal-project-classifier will use these domains to match events to deals
     - Domains like acme.com will match deals with company domain acme.com

5. PAGINATION (Chrome fallback only)
   - Navigate forward day by day through the lookback window
   - For past events, navigate back through --past-days
   - Continue until all dates in the window are processed or hit max_events

6. FINISH
   - Print scan summary using get_scan_status()
   - Report: "X new events saved, Y skipped (duplicates), Z domains matched"
   - Trigger deal-project-classifier if new events were saved
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Calendar Scanner helpers")
    parser.add_argument("--status", action="store_true", help="Show scan status")
    parser.add_argument("--init-db", action="store_true", help="Ensure DB exists")
    parser.add_argument("--lookback-days", type=int, default=7,
                        help="Days forward to scan (default: 7)")
    parser.add_argument("--past-days", type=int, default=1,
                        help="Days back to scan (default: 1)")
    parser.add_argument("--max-events", type=int, default=100)
    parser.add_argument("--calendar", choices=["google", "outlook", "all"],
                        default="all", help="Calendar provider to scan")
    args = parser.parse_args()

    if args.init_db:
        sys.path.insert(0, str(REPO_ROOT / "fund" / "metadata"))
        from init_db import init_db
        init_db(str(DB_PATH))
        print("[VFT] Database ready.")
        sys.exit(0)

    conn = get_db()

    if args.status:
        status = get_scan_status(conn)
        print("[VFT Calendar Scanner Status]")
        print(f"  Total events indexed: {status['total_events']}")
        print(f"  Unclassified: {status['unclassified']}")
        print(f"  Latest event: {status['latest_event_ts']}")
        print(f"  Calendars scanned: {', '.join(status['calendars_scanned']) or 'none'}")
    else:
        provider = get_calendar_provider()
        print("[VFT] Calendar scanner ready.")
        print(f"  Window: {args.past_days}d back + {args.lookback_days}d forward")
        print(f"  Max events: {args.max_events}")
        print(f"  Provider: {args.calendar} (config: {provider})")
        print(f"  Inbox root: {INBOX_ROOT}")
        print(f"  Database: {DB_PATH}")
        status = get_scan_status(conn)
        print(f"  Events indexed so far: {status['total_events']}")

    conn.close()
