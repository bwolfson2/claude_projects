#!/usr/bin/env python3
"""Reactive message router — analyzes classified messages and produces an action plan.

Usage:
    python route_messages.py                    # Route all unrouted messages
    python route_messages.py --dry-run          # Preview without marking as routed
    python route_messages.py --project midbound # Route for a specific project only
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

# ---------------------------------------------------------------------------
# Routing patterns
# ---------------------------------------------------------------------------

ROUTE_RULES = [
    {
        "route": "term_sheet",
        "priority": "URGENT",
        "keywords": [
            "term sheet", "safe agreement", "safe note", "side letter",
            "convertible note", "subscription agreement", "shareholders agreement",
            "stock purchase", "option grant", "board consent",
        ],
        "attachment_patterns": [],
        "actions": ["flag_urgent", "update_deal_stage:term_sheet", "save_to_diligence"],
    },
    {
        "route": "dataroom",
        "priority": "HIGH",
        "keywords": [
            "dataroom", "data room", "diligence materials", "documents attached",
            "shared folder", "drive link", "dropbox link", "files for review",
            "google drive", "box link",
        ],
        "attachment_patterns": [r"\.zip$", r"\.pdf$", r"\.xlsx$"],
        "actions": ["download_attachments", "run_dataroom_intake", "run_document_processor",
                     "update_deal_stage:dataroom_received"],
    },
    {
        "route": "meeting",
        "priority": "MEDIUM",
        "keywords": [
            "schedule", "meeting", "call", "sync", "catch up", "coffee chat",
            "let's connect", "free this week", "calendar invite", "would love to chat",
            "let me know your availability",
        ],
        "attachment_patterns": [r"\.ics$"],
        "actions": ["create_meeting_prep", "update_last_touch"],
    },
    {
        "route": "intro",
        "priority": "MEDIUM",
        "keywords": [
            "introducing", "intro", "connect you with", "wanted to introduce",
            "thought you should meet", "passing along", "meet my friend",
        ],
        "attachment_patterns": [],
        "actions": ["create_deal", "run_web_research", "create_workspace"],
    },
    {
        "route": "funding",
        "priority": "LOW",
        "keywords": [
            "raised", "funding round", "series a", "series b", "seed round",
            "pre-seed", "closed a round", "venture capital",
        ],
        "attachment_patterns": [],
        "actions": ["update_deal_record"],
    },
    {
        "route": "action_items",
        "priority": "LOW",
        "keywords": [
            "i will", "we'll send", "by friday", "by monday", "next week",
            "action item", "follow up on", "please send", "can you send",
            "deadline", "due date",
        ],
        "attachment_patterns": [],
        "actions": ["extract_action_items", "append_next_actions"],
    },
]

# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

def match_route(message: dict) -> list[dict]:
    """Match a message against all routing rules. Returns list of matches sorted by priority."""
    text = " ".join([
        (message.get("subject") or ""),
        (message.get("body") or ""),
    ]).lower()

    attachments_str = (message.get("attachments") or "").lower()

    priority_order = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    matches = []

    for rule in ROUTE_RULES:
        keyword_hits = [kw for kw in rule["keywords"] if kw in text]
        attachment_hits = [p for p in rule["attachment_patterns"]
                          if re.search(p, attachments_str)]

        if keyword_hits or attachment_hits:
            matches.append({
                "route": rule["route"],
                "priority": rule["priority"],
                "actions": rule["actions"],
                "reason": f"Keywords: {keyword_hits}" + (
                    f" | Attachments: {attachment_hits}" if attachment_hits else ""),
                "_priority_num": priority_order.get(rule["priority"], 99),
            })

    matches.sort(key=lambda m: m["_priority_num"])
    # Remove internal sort key
    for m in matches:
        del m["_priority_num"]

    return matches


def route_messages(conn: sqlite3.Connection, project_filter: str = None,
                   dry_run: bool = False) -> list[dict]:
    """Route all unrouted classified messages."""
    conn.row_factory = sqlite3.Row

    query = """
        SELECT m.id, m.source, m.source_id, m.sender, m.subject, m.body,
               m.timestamp, m.attachments, m.channel, m.project_tags,
               cl.matched_slug, cl.match_type, cl.confidence
        FROM messages m
        LEFT JOIN classification_log cl ON m.source_id = cl.source_id AND m.source = cl.source_type
        WHERE m.routed_at IS NULL
    """
    params = []

    if project_filter:
        query += " AND (m.project_tags LIKE ? OR cl.matched_slug LIKE ?)"
        params.extend([f"%{project_filter}%", f"%{project_filter}%"])

    query += " ORDER BY m.timestamp DESC"

    rows = conn.execute(query, params).fetchall()

    action_plan = []

    for row in rows:
        msg = dict(row)
        matches = match_route(msg)

        if not matches:
            continue

        # Take highest priority match as primary
        primary = matches[0]

        entry = {
            "message_id": msg["id"],
            "source": msg["source"],
            "sender": msg["sender"],
            "subject": msg["subject"],
            "timestamp": msg["timestamp"],
            "route": primary["route"],
            "priority": primary["priority"],
            "matched_project": msg.get("matched_slug") or "",
            "actions": primary["actions"],
            "reason": primary["reason"],
        }

        # Include secondary routes if any
        if len(matches) > 1:
            entry["secondary_routes"] = [
                {"route": m["route"], "priority": m["priority"]}
                for m in matches[1:]
            ]

        action_plan.append(entry)

        # Mark as routed (unless dry run)
        if not dry_run:
            conn.execute(
                "UPDATE messages SET routed_at = ? WHERE id = ?",
                (datetime.now().isoformat(), msg["id"])
            )

    if not dry_run:
        conn.commit()

    return action_plan


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Route classified messages to fund workflows")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview routing without marking messages")
    parser.add_argument("--project", type=str, default=None,
                        help="Only route messages for a specific project/deal slug")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")

    action_plan = route_messages(conn, project_filter=args.project, dry_run=args.dry_run)
    conn.close()

    if not action_plan:
        print(json.dumps({"status": "no_actions", "message": "No unrouted messages found matching routing rules"}, indent=2))
        return

    # Group by priority for display
    by_priority = {}
    for entry in action_plan:
        p = entry["priority"]
        by_priority.setdefault(p, []).append(entry)

    summary = {
        "status": "actions_found",
        "dry_run": args.dry_run,
        "total_actions": len(action_plan),
        "by_priority": {k: len(v) for k, v in by_priority.items()},
        "action_plan": action_plan,
    }

    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
