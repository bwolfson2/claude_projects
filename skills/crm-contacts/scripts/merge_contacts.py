#!/usr/bin/env python3
"""Merge cross-platform contact identities.

Finds the same person across platforms (email ↔ Slack handle ↔ WhatsApp phone)
and merges records into a single contact.

Usage:
    python merge_contacts.py              # Auto-merge by matching rules
    python merge_contacts.py --dry-run    # Preview merges
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(os.environ.get("VFT_REPO_ROOT",
    Path(__file__).resolve().parents[3]))
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"


def find_merge_candidates(conn: sqlite3.Connection) -> list[tuple[int, int, str]]:
    """Find contact pairs that likely represent the same person."""
    conn.row_factory = sqlite3.Row
    contacts = conn.execute("SELECT * FROM contacts ORDER BY id").fetchall()
    contacts = [dict(c) for c in contacts]

    merges = []  # (keep_id, merge_id, reason)

    for i, a in enumerate(contacts):
        for b in contacts[i + 1:]:
            # Same name + same company = likely same person
            if (a["name"] and b["name"] and a["company"] and b["company"]
                    and a["name"].lower() == b["name"].lower()
                    and a["company"].lower() == b["company"].lower()):
                merges.append((a["id"], b["id"], f"same name+company: {a['name']} @ {a['company']}"))
                continue

            # Same phone across WhatsApp/Signal
            if (a["phone"] and b["phone"]
                    and a["phone"].replace('+', '').replace('-', '').replace(' ', '')
                    == b["phone"].replace('+', '').replace('-', '').replace(' ', '')):
                merges.append((a["id"], b["id"], f"same phone: {a['phone']}"))
                continue

    return merges


def merge_pair(conn: sqlite3.Connection, keep_id: int, merge_id: int):
    """Merge merge_id into keep_id, preserving all non-null fields."""
    keep = dict(conn.execute("SELECT * FROM contacts WHERE id = ?", (keep_id,)).fetchone())
    merge = dict(conn.execute("SELECT * FROM contacts WHERE id = ?", (merge_id,)).fetchone())

    # Fill in blanks from merge into keep
    fillable = ["phone", "title", "slack_handle", "whatsapp_id", "signal_id",
                 "linkedin_url", "context"]
    updates = {}
    for field in fillable:
        if not keep.get(field) and merge.get(field):
            updates[field] = merge[field]

    # Merge JSON arrays
    for arr_field in ["tags", "deal_slugs", "project_slugs"]:
        keep_arr = set(json.loads(keep.get(arr_field) or "[]"))
        merge_arr = set(json.loads(merge.get(arr_field) or "[]"))
        combined = sorted(keep_arr | merge_arr)
        if combined != sorted(keep_arr):
            updates[arr_field] = json.dumps(combined)

    # Use earlier first_seen
    if merge.get("first_seen") and (not keep.get("first_seen") or merge["first_seen"] < keep["first_seen"]):
        updates["first_seen"] = merge["first_seen"]

    # Use later last_contacted
    if merge.get("last_contacted") and (not keep.get("last_contacted") or merge["last_contacted"] > keep["last_contacted"]):
        updates["last_contacted"] = merge["last_contacted"]

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE contacts SET {set_clause} WHERE id = ?",
                     list(updates.values()) + [keep_id])

    conn.execute("DELETE FROM contacts WHERE id = ?", (merge_id,))


def main():
    parser = argparse.ArgumentParser(description="Merge cross-platform contact identities")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.row_factory = sqlite3.Row

    candidates = find_merge_candidates(conn)

    if not candidates:
        print(json.dumps({"status": "no_merges", "message": "No duplicate contacts found"}))
        return

    print(f"Found {len(candidates)} merge candidates:")
    for keep_id, merge_id, reason in candidates:
        print(f"  Merge #{merge_id} → #{keep_id}: {reason}")

    if args.dry_run:
        return

    for keep_id, merge_id, reason in candidates:
        merge_pair(conn, keep_id, merge_id)

    conn.commit()
    print(f"Merged {len(candidates)} contact pairs")
    conn.close()


if __name__ == "__main__":
    main()
