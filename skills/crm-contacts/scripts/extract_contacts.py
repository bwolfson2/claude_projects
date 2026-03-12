#!/usr/bin/env python3
"""Extract contacts from ingested messages and populate the contacts table.

Scans all messages in ingestion.db, extracts sender/recipient info,
deduplicates by email, and links contacts to deals/projects.

Usage:
    python extract_contacts.py              # Extract from all messages
    python extract_contacts.py --source outlook  # Only from a specific source
    python extract_contacts.py --dry-run    # Preview without writing
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(os.environ.get("VFT_REPO_ROOT",
    Path(__file__).resolve().parents[3]))
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"


def parse_email_name(sender_str: str) -> tuple[str, str]:
    """Extract name and email from sender strings like 'Jane Smith <jane@co.com>' or 'jane@co.com'."""
    # Pattern: Name <email>
    match = re.match(r'^(.+?)\s*<(.+?)>$', sender_str.strip())
    if match:
        return match.group(1).strip().strip('"\''), match.group(2).strip().lower()
    # Pattern: bare email
    email_match = re.match(r'^[\w.+-]+@[\w.-]+\.\w+$', sender_str.strip())
    if email_match:
        email = sender_str.strip().lower()
        local = email.split('@')[0]
        # Try to make a name from the local part
        name = local.replace('.', ' ').replace('_', ' ').replace('-', ' ').title()
        return name, email
    # Not an email — might be a name/handle
    return sender_str.strip(), ""


def domain_to_company(email: str) -> str:
    """Guess company name from email domain."""
    if not email or '@' not in email:
        return ""
    domain = email.split('@')[1].lower()
    # Skip generic providers
    generic = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
               'icloud.com', 'proton.me', 'protonmail.com', 'aol.com',
               'me.com', 'live.com', 'msn.com'}
    if domain in generic:
        return ""
    return domain.split('.')[0].title()


def extract_contacts(conn: sqlite3.Connection, source_filter: str = None,
                     dry_run: bool = False) -> dict:
    """Extract contacts from messages table."""
    conn.row_factory = sqlite3.Row

    query = "SELECT id, source, sender, recipients, timestamp, channel, project_tags FROM messages"
    params = []
    if source_filter:
        query += " WHERE source = ?"
        params.append(source_filter)
    query += " ORDER BY timestamp DESC"

    rows = conn.execute(query, params).fetchall()

    contacts_map = {}  # email -> contact dict
    stats = {"messages_scanned": len(rows), "contacts_found": 0, "new": 0, "updated": 0}

    for row in rows:
        msg = dict(row)
        people = []

        # Extract sender
        if msg["sender"]:
            name, email = parse_email_name(msg["sender"])
            if name:
                people.append((name, email, msg["source"]))

        # Extract recipients
        if msg["recipients"]:
            try:
                recips = json.loads(msg["recipients"])
                if isinstance(recips, list):
                    for r in recips:
                        name, email = parse_email_name(str(r))
                        if name:
                            people.append((name, email, msg["source"]))
            except (json.JSONDecodeError, TypeError):
                # Try as comma-separated string
                for r in str(msg["recipients"]).split(','):
                    name, email = parse_email_name(r.strip())
                    if name:
                        people.append((name, email, msg["source"]))

        # Parse project tags
        project_tags = []
        if msg["project_tags"]:
            try:
                project_tags = json.loads(msg["project_tags"])
            except (json.JSONDecodeError, TypeError):
                pass

        for name, email, source in people:
            if not email:
                continue

            key = email.lower()
            if key not in contacts_map:
                contacts_map[key] = {
                    "name": name,
                    "email": email,
                    "company": domain_to_company(email),
                    "source": source,
                    "first_seen": msg["timestamp"],
                    "last_contacted": msg["timestamp"],
                    "deal_slugs": set(),
                    "project_slugs": set(),
                }
            else:
                # Update last_contacted if newer
                existing = contacts_map[key]
                if msg["timestamp"] and msg["timestamp"] > (existing["last_contacted"] or ""):
                    existing["last_contacted"] = msg["timestamp"]
                if not existing["name"] or len(name) > len(existing["name"]):
                    existing["name"] = name

            # Link to projects/deals
            for tag in project_tags:
                if isinstance(tag, str):
                    contacts_map[key]["deal_slugs"].add(tag)

    stats["contacts_found"] = len(contacts_map)

    if dry_run:
        print(json.dumps(stats, indent=2))
        for email, c in sorted(contacts_map.items()):
            print(f"  {c['name']} <{email}> — {c['company']} (via {c['source']})")
        return stats

    # Upsert into contacts table
    for email, c in contacts_map.items():
        existing = conn.execute("SELECT id FROM contacts WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.execute("""
                UPDATE contacts SET
                    last_contacted = MAX(COALESCE(last_contacted, ''), ?),
                    deal_slugs = ?,
                    project_slugs = ?
                WHERE email = ?
            """, (
                c["last_contacted"],
                json.dumps(sorted(c["deal_slugs"])),
                json.dumps(sorted(c["project_slugs"])),
                email,
            ))
            stats["updated"] += 1
        else:
            conn.execute("""
                INSERT INTO contacts (name, email, company, source, first_seen,
                    last_contacted, deal_slugs, project_slugs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                c["name"], email, c["company"], c["source"],
                c["first_seen"], c["last_contacted"],
                json.dumps(sorted(c["deal_slugs"])),
                json.dumps(sorted(c["project_slugs"])),
            ))
            stats["new"] += 1

    conn.commit()
    print(json.dumps(stats, indent=2))
    return stats


def main():
    parser = argparse.ArgumentParser(description="Extract contacts from ingested messages")
    parser.add_argument("--source", type=str, help="Filter by source (outlook, slack, etc.)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")
    extract_contacts(conn, source_filter=args.source, dry_run=args.dry_run)
    conn.close()


if __name__ == "__main__":
    main()
