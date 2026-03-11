#!/usr/bin/env python3
"""
VFT Signal Scanner — Signal Message Orchestration

This script is designed to be executed by Claude (not run standalone).
It provides the logic and state management for scanning Signal messages
via signal-cli (preferred) or Claude in Chrome on Signal Desktop (fallback).
Claude reads this script, follows the workflow, and uses the appropriate
tools to interact with Signal.

Usage (by Claude):
    Read this script, then follow the WORKFLOW section using the appropriate mode.
    Call the helper functions via python to manage state and persistence.

Standalone helpers:
    python scan_signal.py --status         # Show scan status
    python scan_signal.py --check-cli      # Check if signal-cli is available
    python scan_signal.py --init-db        # Ensure DB schema exists
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[3]  # skills/signal-scanner/scripts → repo root
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"
INBOX_ROOT = REPO_ROOT / "fund" / "inbox" / "signal"


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


def make_source_id(sender: str, timestamp: str) -> str:
    """Generate a dedup key from message metadata."""
    return f"{sender}|{timestamp}"


def is_already_scanned(conn: sqlite3.Connection, source_id: str) -> bool:
    """Check if a message has already been ingested."""
    row = conn.execute(
        "SELECT id FROM messages WHERE source_id = ?", (source_id,)
    ).fetchone()
    return row is not None


def check_signal_cli() -> dict:
    """
    Check if signal-cli is installed and available.
    Returns a dict with status info.
    """
    cli_path = shutil.which("signal-cli")
    if cli_path is None:
        return {
            "available": False,
            "path": None,
            "reason": "signal-cli not found in PATH",
        }

    try:
        result = subprocess.run(
            ["signal-cli", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        version = result.stdout.strip() if result.returncode == 0 else None
        return {
            "available": result.returncode == 0,
            "path": cli_path,
            "version": version,
            "reason": None if result.returncode == 0 else result.stderr.strip(),
        }
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {
            "available": False,
            "path": cli_path,
            "reason": str(e),
        }


def save_message(
    conn: sqlite3.Connection,
    sender: str,
    timestamp: str,
    channel: str,
    body: str,
    attachments: list = None,
    attachment_paths: list = None,
) -> dict:
    """
    Save a Signal message to the filesystem and index in the database.
    Returns a dict with the saved paths and database id.
    """
    source_id = make_source_id(sender, timestamp)

    if is_already_scanned(conn, source_id):
        return {"status": "skipped", "reason": "already_scanned", "source_id": source_id}

    # Determine folder
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        dt = datetime.now()

    month_folder = dt.strftime("%Y-%m")
    channel_slug = slugify(channel)

    # Ensure unique folder
    folder = INBOX_ROOT / month_folder / channel_slug
    counter = 2
    base_folder = folder
    while folder.exists():
        folder = base_folder.parent / f"{base_folder.name}-{counter}"
        counter += 1

    folder.mkdir(parents=True, exist_ok=True)

    # Write message.md
    message_md = folder / "message.md"
    attachment_list = ", ".join(attachments) if attachments else "None"
    content = f"""# Signal: {channel}

**From:** {sender}
**Channel:** {channel}
**Date:** {timestamp}
**Attachments:** {attachment_list}

---

{body}
"""
    message_md.write_text(content, encoding="utf-8")

    # Relative path for DB
    rel_folder = str(folder.relative_to(REPO_ROOT))
    abs_path = str(message_md)

    # Insert into DB
    conn.execute(
        """INSERT INTO messages
           (source, type, source_id, channel, sender, timestamp, body_preview,
            folder_saved_to, raw_path, has_attachments, attachment_paths)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "signal",
            "message",
            source_id,
            channel,
            sender,
            timestamp,
            body[:500] if body else "",
            rel_folder,
            abs_path,
            1 if attachments else 0,
            json.dumps(attachment_paths or []),
        ),
    )
    conn.commit()

    message_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    return {
        "status": "saved",
        "id": message_id,
        "folder": str(folder),
        "message_md": str(message_md),
        "source_id": source_id,
    }


def get_scan_status(conn: sqlite3.Connection) -> dict:
    """Get current scan statistics for Signal messages."""
    total = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE source = 'signal'"
    ).fetchone()[0]
    unclassified = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE source = 'signal' AND classified = 0"
    ).fetchone()[0]
    latest = conn.execute(
        "SELECT timestamp FROM messages WHERE source = 'signal' ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()

    return {
        "total_messages": total,
        "unclassified": unclassified,
        "latest_message_date": latest[0] if latest else "none",
    }


# ── WORKFLOW (for Claude to follow) ──────────────────────────────────────
"""
CLAUDE WORKFLOW:

1. DETECT MODE
   - Call check_signal_cli() to see if signal-cli is available
   - If available: use signal-cli mode (preferred)
   - If unavailable: fall back to Chrome on Signal Desktop mode
   - Log which mode is active

2A. SIGNAL-CLI MODE
   - Run: signal-cli -u <number> receive --json
   - Parse each JSON line from stdout
   - For each message envelope:
     a. Extract sender from envelope.source
     b. Extract timestamp from envelope.timestamp (epoch ms → ISO)
     c. Extract group from envelope.dataMessage.groupInfo.groupId (if present)
     d. Extract body from envelope.dataMessage.message
     e. Extract attachments from envelope.dataMessage.attachments (if present)
   - Resolve group IDs to names via: signal-cli -u <number> listGroups
   - Call save_message() for each extracted message

2B. CHROME ON SIGNAL DESKTOP MODE
   - Use navigate tool to open Signal Desktop or Signal Web
   - Use read_page to get the conversation list
   - For each conversation with recent activity:
     a. Click the conversation to open the thread
     b. Use get_page_text to extract messages
     c. Extract sender, timestamp, channel from the message view
     d. Extract body text from each message bubble
     e. Check for media/file attachments
   - Call save_message() for each extracted message
   - Navigate back to the conversation list and continue

3. FOR EACH MESSAGE:
   - Call save_message() with the extracted metadata
   - If attachments exist:
     - signal-cli: attachments are saved to a local folder, copy them
     - Chrome: click download on each attachment, note the filename
   - Save attachment paths

4. PAGINATION / SCROLLING
   - signal-cli: all pending messages are returned at once
   - Chrome: scroll up in conversations to load older messages within the lookback window
   - Continue until all messages in the window are processed or max_messages is reached

5. FINISH
   - Print scan summary (new messages saved, skipped, errors)
   - Trigger deal-project-classifier if new messages were saved
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Signal Scanner helpers")
    parser.add_argument("--status", action="store_true", help="Show scan status")
    parser.add_argument("--check-cli", action="store_true", help="Check signal-cli availability")
    parser.add_argument("--init-db", action="store_true", help="Ensure DB exists")
    parser.add_argument("--lookback-hours", type=int, default=4)
    parser.add_argument("--max-messages", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    if args.init_db:
        sys.path.insert(0, str(REPO_ROOT / "fund" / "metadata"))
        from init_db import init_db
        init_db(str(DB_PATH))
        print("[VFT] Database ready.")
        sys.exit(0)

    if args.check_cli:
        cli_info = check_signal_cli()
        print(f"[VFT Signal Scanner — signal-cli check]")
        print(f"  Available: {cli_info['available']}")
        print(f"  Path: {cli_info.get('path', 'N/A')}")
        if cli_info.get("version"):
            print(f"  Version: {cli_info['version']}")
        if cli_info.get("reason"):
            print(f"  Reason: {cli_info['reason']}")
        sys.exit(0 if cli_info["available"] else 1)

    conn = get_db()

    if args.status:
        status = get_scan_status(conn)
        print(f"[VFT Signal Scanner Status]")
        print(f"  Total messages indexed: {status['total_messages']}")
        print(f"  Unclassified: {status['unclassified']}")
        print(f"  Latest message: {status['latest_message_date']}")
    else:
        cli_info = check_signal_cli()
        mode = "signal-cli" if cli_info["available"] else "chrome"
        print(f"[VFT] Signal scanner ready.")
        print(f"  Mode: {mode}")
        print(f"  Lookback: {args.lookback_hours}h | Max: {args.max_messages} messages")
        print(f"  Inbox root: {INBOX_ROOT}")
        print(f"  Database: {DB_PATH}")
        status = get_scan_status(conn)
        print(f"  Messages indexed so far: {status['total_messages']}")
        if args.dry_run:
            print(f"  ** DRY RUN — no messages will be saved **")

    conn.close()
