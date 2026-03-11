#!/usr/bin/env python3
"""
VFT Email Scanner — Outlook Web Orchestration

This script is designed to be executed by Claude (not run standalone).
It provides the logic and state management for scanning Outlook emails
via Claude in Chrome. Claude reads this script, follows the workflow,
and uses the browser tools to interact with Outlook.

Usage (by Claude):
    Read this script, then follow the WORKFLOW section using Claude in Chrome tools.
    Call the helper functions via python to manage state and persistence.

Standalone helpers:
    python scan_outlook.py --status         # Show scan status
    python scan_outlook.py --init-db        # Ensure DB schema exists
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
REPO_ROOT = Path(__file__).resolve().parents[3]  # skills/email-scanner/scripts → repo root
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"
INBOX_ROOT = REPO_ROOT / "fund" / "inbox"
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


def extract_domain(email_addr: str) -> str:
    """Extract domain from an email address."""
    if "@" in email_addr:
        return email_addr.split("@")[-1].lower().strip()
    return ""


def make_outlook_id(sender: str, date: str, subject: str) -> str:
    """Generate a dedup key from email metadata."""
    return f"{sender}|{date}|{subject[:50]}"


def is_already_scanned(conn: sqlite3.Connection, outlook_id: str) -> bool:
    """Check if an email has already been ingested."""
    row = conn.execute(
        "SELECT id FROM emails WHERE outlook_id = ?", (outlook_id,)
    ).fetchone()
    return row is not None


def save_email(
    conn: sqlite3.Connection,
    subject: str,
    sender: str,
    recipients: str,
    date: str,
    body: str,
    attachments: list = None,
    attachment_paths: list = None,
) -> dict:
    """
    Save an email to the filesystem and index in the database.
    Returns a dict with the saved paths and database id.
    """
    outlook_id = make_outlook_id(sender, date, subject)

    if is_already_scanned(conn, outlook_id):
        return {"status": "skipped", "reason": "already_scanned", "outlook_id": outlook_id}

    # Determine folder
    try:
        dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        dt = datetime.now()

    month_folder = dt.strftime("%Y-%m")
    email_slug = slugify(subject)

    # Ensure unique folder
    folder = INBOX_ROOT / month_folder / email_slug
    counter = 2
    base_folder = folder
    while folder.exists():
        folder = base_folder.parent / f"{base_folder.name}-{counter}"
        counter += 1

    folder.mkdir(parents=True, exist_ok=True)

    # Write email.md
    email_md = folder / "email.md"
    attachment_list = ", ".join(attachments) if attachments else "None"
    content = f"""# {subject}

**From:** {sender}
**To:** {recipients}
**Date:** {date}
**Attachments:** {attachment_list}

---

{body}
"""
    email_md.write_text(content, encoding="utf-8")

    # Relative path for DB
    rel_folder = str(folder.relative_to(REPO_ROOT))
    abs_path = str(email_md)
    sender_domain = extract_domain(sender)

    # Insert into DB
    conn.execute(
        """INSERT INTO emails
           (outlook_id, subject, sender, sender_domain, recipients, date,
            body_preview, folder_saved_to, raw_path, has_attachments, attachment_paths)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            outlook_id,
            subject,
            sender,
            sender_domain,
            recipients,
            date,
            body[:500] if body else "",
            rel_folder,
            abs_path,
            1 if attachments else 0,
            json.dumps(attachment_paths or []),
        ),
    )

    email_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Also write to unified messages table (v2)
    recipients_list = [r.strip() for r in (recipients or "").split(",") if r.strip()]
    attachments_json = []
    if attachment_paths:
        attachments_json = [{"name": os.path.basename(p), "path": p} for p in attachment_paths]

    try:
        conn.execute(
            """INSERT OR IGNORE INTO messages
               (source, source_id, type, sender, recipients, subject, body,
                timestamp, channel, attachments, project_tags, raw_path,
                metadata, classified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "outlook",
                outlook_id,
                "email",
                sender,
                json.dumps(recipients_list),
                subject,
                body[:500] if body else "",
                date,
                "inbox",
                json.dumps(attachments_json),
                "[]",
                abs_path,
                json.dumps({"sender_domain": sender_domain, "folder_saved_to": rel_folder, "legacy_email_id": email_id}),
                0,
            ),
        )
    except Exception:
        pass  # Unified table may not exist in older schema — graceful degradation

    conn.commit()

    return {
        "status": "saved",
        "id": email_id,
        "folder": str(folder),
        "email_md": str(email_md),
        "outlook_id": outlook_id,
    }


def get_scan_status(conn: sqlite3.Connection) -> dict:
    """Get current scan statistics."""
    total = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
    unclassified = conn.execute(
        "SELECT COUNT(*) FROM emails WHERE classified = 0"
    ).fetchone()[0]
    latest = conn.execute(
        "SELECT date FROM emails ORDER BY date DESC LIMIT 1"
    ).fetchone()

    return {
        "total_emails": total,
        "unclassified": unclassified,
        "latest_email_date": latest[0] if latest else "none",
    }


# ── WORKFLOW (for Claude to follow) ──────────────────────────────────────
"""
CLAUDE IN CHROME WORKFLOW:

1. NAVIGATE
   - Use navigate tool to go to: https://outlook.cloud.microsoft/mail/
   - Verify you're on the bw@vft.institute account
   - If auth required, stop and notify the user

2. SCAN INBOX
   - Use read_page to get the email list
   - For each email in the visible list:
     a. Click the email to open it
     b. Use get_page_text to extract the full content
     c. Extract: subject, sender, recipients, date from the header
     d. Extract body text
     e. Check for attachments

3. FOR EACH EMAIL:
   - Call save_email() with the extracted metadata
   - If attachments exist:
     - Click each attachment's download button
     - Note the downloaded filename
     - Save attachment paths

4. PAGINATION
   - Scroll down to load more emails if within the lookback window
   - Continue until you've processed all emails in the window or hit max_emails

5. FINISH
   - Print scan summary
   - Trigger deal-project-classifier if new emails were saved
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Email Scanner helpers")
    parser.add_argument("--status", action="store_true", help="Show scan status")
    parser.add_argument("--init-db", action="store_true", help="Ensure DB exists")
    parser.add_argument("--lookback-hours", type=int, default=4)
    parser.add_argument("--max-emails", type=int, default=50)
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
        print(f"[VFT Email Scanner Status]")
        print(f"  Total emails indexed: {status['total_emails']}")
        print(f"  Unclassified: {status['unclassified']}")
        print(f"  Latest email: {status['latest_email_date']}")
    else:
        print(f"[VFT] Email scanner ready.")
        print(f"  Lookback: {args.lookback_hours}h | Max: {args.max_emails} emails")
        print(f"  Inbox root: {INBOX_ROOT}")
        print(f"  Database: {DB_PATH}")
        status = get_scan_status(conn)
        print(f"  Emails indexed so far: {status['total_emails']}")

    conn.close()
