#!/usr/bin/env python3
"""Export contacts table to fund/crm/contacts.json.

Usage:
    python sync_contacts.py
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(os.environ.get("VFT_REPO_ROOT",
    Path(__file__).resolve().parents[3]))
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"
CONTACTS_JSON = REPO_ROOT / "fund" / "crm" / "contacts.json"


def export_contacts():
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT name, email, phone, company, title,
               slack_handle, whatsapp_id, signal_id, linkedin_url,
               tags, context, deal_slugs, project_slugs,
               first_seen, last_contacted, source
        FROM contacts
        ORDER BY last_contacted DESC NULLS LAST, name
    """).fetchall()

    contacts = []
    for row in rows:
        c = dict(row)
        # Parse JSON fields
        for field in ["tags", "deal_slugs", "project_slugs"]:
            try:
                c[field] = json.loads(c[field]) if c[field] else []
            except (json.JSONDecodeError, TypeError):
                c[field] = []
        contacts.append(c)

    CONTACTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(CONTACTS_JSON, "w") as f:
        json.dump(contacts, f, indent=2)

    print(f"Exported {len(contacts)} contacts to {CONTACTS_JSON}")
    conn.close()


if __name__ == "__main__":
    export_contacts()
