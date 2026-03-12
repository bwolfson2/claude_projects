#!/usr/bin/env python3
"""
VFT WhatsApp Scanner — WhatsApp Web Orchestration

This script is designed to be executed by Claude (not run standalone).
It provides the logic and state management for scanning WhatsApp Web
messages via Claude in Chrome. Claude reads this script, follows the
workflow, and uses the browser tools to interact with WhatsApp Web.

Usage (by Claude):
    Read this script, then follow the WORKFLOW section using Claude in Chrome tools.
    Call the helper functions via python to manage state and persistence.

Standalone helpers:
    python scan_whatsapp.py --status         # Show scan status
    python scan_whatsapp.py --init-db        # Ensure DB schema exists
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
REPO_ROOT = Path(__file__).resolve().parents[3]  # skills/whatsapp-scanner/scripts → repo root
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"
INBOX_ROOT = REPO_ROOT / "fund" / "inbox" / "whatsapp"

# ── Config ───────────────────────────────────────────────────────────────
CONFIG_PATH = REPO_ROOT / "fund" / "metadata" / "config.json"

# ── Scan Targets ─────────────────────────────────────────────────────────
# Add or remove groups and contacts to monitor here.
# Keys are the display names as they appear in WhatsApp Web.
# "type" is either "group" or "direct".
# If fund/metadata/config.json exists with whatsapp targets, those are used instead.
_HARDCODED_TARGETS = {
    # "VFT Deal Flow": {"type": "group"},
    # "Founders Chat": {"type": "group"},
    # "John Doe": {"type": "direct"},
}


def _load_targets_from_config() -> dict:
    """Load WhatsApp scan targets from config.json if available."""
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text())
            wa_config = config.get("channels", {}).get("whatsapp", {})
            if wa_config.get("enabled") and wa_config.get("targets"):
                targets = {}
                for name in wa_config["targets"]:
                    if isinstance(name, dict):
                        targets[name.get("name", str(name))] = {"type": name.get("type", "group")}
                    else:
                        targets[str(name)] = {"type": "group"}
                return targets
        except (json.JSONDecodeError, IOError):
            pass
    return _HARDCODED_TARGETS


SCAN_TARGETS = _load_targets_from_config()


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


def make_source_id(chat_slug: str, sender: str, timestamp: str) -> str:
    """Generate a dedup key from message metadata."""
    return f"{chat_slug}|{sender}|{timestamp}"


def is_already_scanned(conn: sqlite3.Connection, source_id: str) -> bool:
    """Check if a message has already been ingested."""
    row = conn.execute(
        "SELECT id FROM messages WHERE source = 'whatsapp' AND source_id = ?",
        (source_id,),
    ).fetchone()
    return row is not None


def save_message(
    conn: sqlite3.Connection,
    chat_name: str,
    chat_type: str,
    sender: str,
    body: str,
    timestamp: str,
) -> dict:
    """
    Save a WhatsApp message to the filesystem and index in the database.
    Returns a dict with the saved paths and database id.

    Args:
        conn: Database connection
        chat_name: Group name or contact name as shown in WhatsApp
        chat_type: "group" or "direct"
        sender: Sender name as shown in the message
        body: Full message text
        timestamp: ISO-8601 formatted timestamp (YYYY-MM-DD HH:MM or full ISO)
    """
    chat_slug = slugify(chat_name)
    source_id = make_source_id(chat_slug, sender, timestamp)

    if is_already_scanned(conn, source_id):
        return {"status": "skipped", "reason": "already_scanned", "source_id": source_id}

    # Determine folder
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        dt = datetime.now()

    month_folder = dt.strftime("%Y-%m")

    # Save to fund/inbox/whatsapp/{YYYY-MM}/{chat-slug}/
    folder = INBOX_ROOT / month_folder / chat_slug
    folder.mkdir(parents=True, exist_ok=True)

    # Append to messages.md (one file per chat per month)
    messages_md = folder / "messages.md"

    if not messages_md.exists():
        header = f"""# {chat_name}

**Scanned:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**Source:** WhatsApp Web

---

"""
        messages_md.write_text(header, encoding="utf-8")

    # Append the new message
    entry = f"""### {sender} — {timestamp}
{body}

"""
    with open(messages_md, "a", encoding="utf-8") as f:
        f.write(entry)

    # Relative path for DB
    abs_path = str(messages_md)

    # Build recipients based on chat type
    recipients = json.dumps([]) if chat_type == "group" else json.dumps([chat_name])

    # Build metadata
    metadata = json.dumps({"chat_type": chat_type})

    # Insert into unified messages table
    conn.execute(
        """INSERT OR IGNORE INTO messages
           (source, source_id, type, sender, recipients, subject, body,
            timestamp, channel, attachments, project_tags, raw_path,
            metadata, classified)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "whatsapp",
            source_id,
            "message",
            sender,
            recipients,
            None,  # WhatsApp messages don't have subjects
            body,
            timestamp,
            chat_name,
            "[]",  # attachments — not supported in initial version
            "[]",  # project_tags — populated by classifier
            abs_path,
            metadata,
            0,  # classified
        ),
    )
    conn.commit()

    msg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    return {
        "status": "saved",
        "id": msg_id,
        "folder": str(folder),
        "messages_md": str(messages_md),
        "source_id": source_id,
    }


def get_scan_status(conn: sqlite3.Connection) -> dict:
    """Get current WhatsApp scan statistics."""
    total = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE source = 'whatsapp'"
    ).fetchone()[0]
    unclassified = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE source = 'whatsapp' AND classified = 0"
    ).fetchone()[0]
    latest = conn.execute(
        "SELECT timestamp FROM messages WHERE source = 'whatsapp' ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    channels = conn.execute(
        "SELECT DISTINCT channel FROM messages WHERE source = 'whatsapp'"
    ).fetchall()

    return {
        "total_messages": total,
        "unclassified": unclassified,
        "latest_message": latest[0] if latest else "none",
        "channels": [row[0] for row in channels],
    }


def get_scan_targets() -> dict:
    """Return the configured scan targets."""
    return SCAN_TARGETS


# ── WORKFLOW (for Claude to follow) ──────────────────────────────────────
"""
CLAUDE WHATSAPP SCANNING WORKFLOW:

1. CHECK CONNECTOR
   - Search for a WhatsApp MCP connector using mcp-registry search
   - If available and connected, prefer MCP tools for steps 2-6
   - If not available, use Claude in Chrome browser automation (steps below)

2. NAVIGATE (browser fallback)
   - Use navigate tool to go to: https://web.whatsapp.com/
   - Use read_page to verify the session is active (chat list visible)
   - If QR code screen is shown, stop and notify the user

3. GET TARGETS
   - Call get_scan_targets() to get the configured groups/contacts
   - If no targets are configured, notify the user and stop

4. FOR EACH TARGET:
   a. Use the search bar at the top of the chat list
   b. Type the group/contact name
   c. Use read_page to find the matching result in the search dropdown
   d. Click the result to open the chat
   e. Wait for the chat to load

5. READ MESSAGES
   - Use read_page to get the message list accessibility tree
   - Track date separator elements to build full timestamps
   - For each message within the lookback window:
     i.   Extract sender name, text, and timestamp
     ii.  Build the full ISO-8601 timestamp
     iii. Call is_already_scanned() to check if already ingested
     iv.  If new, call save_message() with the extracted data
   - Scroll up to load older messages if still within the lookback window

6. NAVIGATE TO NEXT TARGET
   - Click the back arrow or use the search bar for the next chat
   - Repeat steps 4-5 for each target

7. FINISH
   - Print scan summary (new messages saved, skipped, errors)
   - Trigger deal-project-classifier if new messages were saved
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT WhatsApp Scanner helpers")
    parser.add_argument("--status", action="store_true", help="Show scan status")
    parser.add_argument("--init-db", action="store_true", help="Ensure DB exists")
    parser.add_argument("--lookback-hours", type=int, default=4)
    parser.add_argument("--max-messages", type=int, default=200)
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
        print(f"[VFT WhatsApp Scanner Status]")
        print(f"  Total messages indexed: {status['total_messages']}")
        print(f"  Unclassified: {status['unclassified']}")
        print(f"  Latest message: {status['latest_message']}")
        print(f"  Channels: {', '.join(status['channels']) if status['channels'] else 'none'}")
    else:
        print(f"[VFT] WhatsApp scanner ready.")
        print(f"  Lookback: {args.lookback_hours}h | Max: {args.max_messages} messages")
        print(f"  Inbox root: {INBOX_ROOT}")
        print(f"  Database: {DB_PATH}")
        targets = get_scan_targets()
        print(f"  Configured targets: {len(targets)}")
        for name, cfg in targets.items():
            print(f"    - {name} ({cfg['type']})")
        status = get_scan_status(conn)
        print(f"  Messages indexed so far: {status['total_messages']}")

    conn.close()
