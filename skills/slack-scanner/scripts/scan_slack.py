#!/usr/bin/env python3
"""
VFT Slack Scanner — Slack Web / MCP Orchestration

This script is designed to be executed by Claude (not run standalone).
It provides the logic and state management for scanning Slack messages
via Claude in Chrome or the Slack MCP connector. Claude reads this script,
follows the workflow, and uses the browser tools (or MCP tools) to interact
with Slack.

Usage (by Claude):
    Read this script, then follow the WORKFLOW section using Claude in Chrome tools
    (or Slack MCP tools if available).
    Call the helper functions via python to manage state and persistence.

Standalone helpers:
    python scan_slack.py --status         # Show scan status
    python scan_slack.py --init-db        # Ensure DB schema exists
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
REPO_ROOT = Path(__file__).resolve().parents[3]  # skills/slack-scanner/scripts → repo root
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"
SLACK_INBOX_ROOT = REPO_ROOT / "fund" / "inbox" / "slack"
DEALS_PATH = REPO_ROOT / "fund" / "crm" / "deals.json"

# ── Constants ────────────────────────────────────────────────────────────
DEFAULT_WORKSPACE = "vft"
SOURCE = "slack"


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


def make_source_id(workspace: str, channel_id: str, message_ts: str) -> str:
    """Generate a dedup key from Slack message identifiers."""
    return f"{workspace}|{channel_id}|{message_ts}"


def is_already_scanned(conn: sqlite3.Connection, source_id: str) -> bool:
    """Check if a message has already been ingested."""
    row = conn.execute(
        "SELECT id FROM messages WHERE source = ? AND source_id = ?",
        (SOURCE, source_id),
    ).fetchone()
    return row is not None


def save_message(
    conn: sqlite3.Connection,
    sender: str,
    timestamp: str,
    channel_name: str,
    channel_id: str,
    message_ts: str,
    body: str,
    msg_type: str = "message",
    thread_replies: list = None,
    attachments: list = None,
    attachment_paths: list = None,
    workspace: str = DEFAULT_WORKSPACE,
    thread_ts: str = "",
    permalink: str = "",
    recipients: list = None,
) -> dict:
    """
    Save a Slack message to the filesystem and index in the database.
    Returns a dict with the saved paths and database id.

    Writes to BOTH:
    - The filesystem at fund/inbox/slack/{YYYY-MM}/{channel-slug}/
    - The unified messages table in the ingestion database
    """
    source_id = make_source_id(workspace, channel_id, message_ts)

    if is_already_scanned(conn, source_id):
        return {"status": "skipped", "reason": "already_scanned", "source_id": source_id}

    # Determine folder
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        dt = datetime.now()

    month_folder = dt.strftime("%Y-%m")
    date_str = dt.strftime("%Y-%m-%d")
    channel_slug = slugify(channel_name)

    # Build folder path
    folder = SLACK_INBOX_ROOT / month_folder / channel_slug
    folder.mkdir(parents=True, exist_ok=True)

    # Build message file path (one file per day per channel, append if exists)
    msg_file = folder / f"messages-{date_str}.md"

    # Build message content
    thread_text = ""
    if thread_replies:
        thread_lines = []
        for reply in thread_replies:
            reply_sender = reply.get("sender", "Unknown")
            reply_time = reply.get("time", "")
            reply_body = reply.get("body", "")
            thread_lines.append(f"- **{reply_sender}** ({reply_time}): {reply_body}")
        thread_text = f"\n\n#### Thread ({len(thread_replies)} replies)\n" + "\n".join(thread_lines)

    time_str = dt.strftime("%H:%M")
    msg_block = f"\n### {sender} -- {time_str}\n{body}{thread_text}\n"

    # If file already exists, append; otherwise write header
    if msg_file.exists():
        with open(msg_file, "a", encoding="utf-8") as f:
            f.write(msg_block)
    else:
        header = f"# #{channel_name} -- {date_str}\n\n## Messages\n"
        msg_file.write_text(header + msg_block, encoding="utf-8")

    # Relative path for DB
    rel_folder = str(folder.relative_to(REPO_ROOT))
    abs_path = str(msg_file)

    # Build full body for DB (include thread replies)
    full_body = body
    if thread_replies:
        for reply in thread_replies:
            full_body += f"\n[{reply.get('sender', '')}]: {reply.get('body', '')}"

    # Build channel display name
    if channel_name.startswith("dm-"):
        channel_display = f"DM: {channel_name[3:].replace('-', ' ').title()}"
    else:
        channel_display = f"#{channel_name}"

    # Prepare attachments JSON
    attachments_json = json.dumps(
        [{"name": a, "path": p} for a, p in zip(attachments or [], attachment_paths or [])]
    )

    # Prepare metadata JSON
    metadata = json.dumps({
        "workspace": workspace,
        "channel_id": channel_id,
        "message_ts": message_ts,
        "thread_ts": thread_ts,
        "permalink": permalink,
    })

    # Insert into unified messages table
    try:
        conn.execute(
            """INSERT OR IGNORE INTO messages
               (source, source_id, type, sender, recipients, subject, body,
                timestamp, channel, attachments, project_tags, raw_path,
                metadata, classified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                SOURCE,
                source_id,
                msg_type,
                sender,
                json.dumps(recipients or []),
                channel_name,
                full_body[:5000] if full_body else "",
                timestamp,
                channel_display,
                attachments_json,
                json.dumps([]),
                abs_path,
                metadata,
                0,
            ),
        )
        conn.commit()
    except Exception as e:
        # Retry up to 3 times on database lock
        retries = 3
        for attempt in range(retries):
            try:
                import time
                time.sleep(2)
                conn.execute(
                    """INSERT OR IGNORE INTO messages
                       (source, source_id, type, sender, recipients, subject, body,
                        timestamp, channel, attachments, project_tags, raw_path,
                        metadata, classified)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        SOURCE,
                        source_id,
                        msg_type,
                        sender,
                        json.dumps(recipients or []),
                        channel_name,
                        full_body[:5000] if full_body else "",
                        timestamp,
                        channel_display,
                        attachments_json,
                        json.dumps([]),
                        abs_path,
                        metadata,
                        0,
                    ),
                )
                conn.commit()
                break
            except Exception:
                if attempt == retries - 1:
                    return {"status": "error", "reason": str(e), "source_id": source_id}

    message_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    return {
        "status": "saved",
        "id": message_id,
        "folder": str(folder),
        "file": str(msg_file),
        "source_id": source_id,
    }


def get_scan_status(conn: sqlite3.Connection) -> dict:
    """Get current scan statistics for Slack messages."""
    # Unified messages table
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

    channels = conn.execute(
        "SELECT DISTINCT channel FROM messages WHERE source = ?", (SOURCE,)
    ).fetchall()

    return {
        "total_messages": total,
        "unclassified": unclassified,
        "latest_message_ts": latest[0] if latest else "none",
        "channels_scanned": [r[0] for r in channels],
    }


def get_last_scan_timestamp(conn: sqlite3.Connection) -> str:
    """Get the timestamp of the most recently scanned Slack message."""
    row = conn.execute(
        "SELECT MAX(timestamp) FROM messages WHERE source = ?", (SOURCE,)
    ).fetchone()
    return row[0] if row and row[0] else ""


# ── WORKFLOW (for Claude to follow) ──────────────────────────────────────
"""
CLAUDE SLACK SCANNING WORKFLOW:

1. CHECK CONNECTOR
   - Search for a Slack MCP connector using mcp-registry search
   - If available and connected, prefer MCP tools for steps 2-4
   - If not available, use Claude in Chrome browser automation

2. NAVIGATE (browser fallback)
   - Use navigate tool to go to: https://app.slack.com/
   - Verify you're on the VFT workspace
   - If auth required, stop and notify the user

3. SCAN CHANNELS
   - Use read_page to get the channel sidebar
   - Identify channels with recent activity (unread indicators)
   - For each active channel/DM:
     a. Click the channel to open it
     b. Use get_page_text to extract visible messages
     c. Extract: sender, timestamp, channel name, message text
     d. Look for thread indicators ("N replies") and expand them
     e. Check for file attachments

4. FOR EACH MESSAGE:
   - Build the source_id: make_source_id(workspace, channel_id, message_ts)
   - Call is_already_scanned() to check for duplicates
   - If new, call save_message() with the extracted data
   - For threads: set msg_type="thread" and include thread_replies list
   - If attachments exist:
     - Click each file's download button
     - Note the downloaded filename
     - Pass attachment names and paths to save_message()

5. PAGINATION
   - Scroll up in channels to load older messages if within the lookback window
   - Move to the next channel after processing all messages in the window
   - Continue until all active channels are processed or hit max_messages

6. FINISH
   - Print scan summary using get_scan_status()
   - Trigger deal-project-classifier if new messages were saved
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Slack Scanner helpers")
    parser.add_argument("--status", action="store_true", help="Show scan status")
    parser.add_argument("--init-db", action="store_true", help="Ensure DB exists")
    parser.add_argument("--lookback-hours", type=int, default=2)
    parser.add_argument("--max-messages", type=int, default=200)
    parser.add_argument("--channels", type=str, default="", help="Comma-separated channel names")
    parser.add_argument("--dry-run", action="store_true")
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
        print(f"[VFT Slack Scanner Status]")
        print(f"  Total messages indexed: {status['total_messages']}")
        print(f"  Unclassified: {status['unclassified']}")
        print(f"  Latest message: {status['latest_message_ts']}")
        print(f"  Channels scanned: {', '.join(status['channels_scanned']) or 'none'}")
        last = get_last_scan_timestamp(conn)
        print(f"  Last scan timestamp: {last or 'never'}")
    else:
        channels_filter = args.channels.split(",") if args.channels else []
        print(f"[VFT] Slack scanner ready.")
        print(f"  Lookback: {args.lookback_hours}h | Max: {args.max_messages} messages")
        if channels_filter:
            print(f"  Channels filter: {', '.join(channels_filter)}")
        else:
            print(f"  Channels: all active")
        print(f"  Inbox root: {SLACK_INBOX_ROOT}")
        print(f"  Database: {DB_PATH}")
        status = get_scan_status(conn)
        print(f"  Slack messages indexed so far: {status['total_messages']}")

    conn.close()
