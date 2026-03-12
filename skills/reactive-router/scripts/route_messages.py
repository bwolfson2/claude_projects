#!/usr/bin/env python3
"""
VFT Reactive Router — RLM Data Access CLI

Provides subcommands for Claude Code to drive message routing conversationally.
Instead of pattern matching against keyword rules, Claude reads pending messages
and their classification context, then decides what actions the fund should take.

    python route_messages.py pending                    # List classified-but-unrouted messages
    python route_messages.py routes                     # Show available route types
    python route_messages.py route --message-id 42 --route dataroom --priority HIGH --actions '[...]'
    python route_messages.py batch-route --decisions '[...]'
    python route_messages.py mark-routed --message-ids 1,2,3
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(os.environ.get("VFT_REPO_ROOT",
    Path(__file__).resolve().parents[3]))
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"

# Available route types — reference data for Claude's reasoning
ROUTE_DEFINITIONS = [
    {
        "route": "term_sheet",
        "priority": "URGENT",
        "description": "Term sheet, SAFE, convertible note, or legal investment document received",
        "typical_actions": ["flag_urgent", "update_deal_stage:term_sheet", "save_to_diligence"],
    },
    {
        "route": "dataroom",
        "priority": "HIGH",
        "description": "Dataroom or diligence materials shared (zip, folder link, document batch)",
        "typical_actions": ["download_attachments", "run_dataroom_intake",
                            "run_document_processor", "update_deal_stage:dataroom_received"],
    },
    {
        "route": "meeting",
        "priority": "MEDIUM",
        "description": "Meeting request, calendar invite, or scheduling discussion",
        "typical_actions": ["create_meeting_prep", "update_last_touch"],
    },
    {
        "route": "intro",
        "priority": "MEDIUM",
        "description": "New introduction to a founder, company, or opportunity",
        "typical_actions": ["create_deal", "run_web_research", "create_workspace"],
    },
    {
        "route": "funding",
        "priority": "LOW",
        "description": "Funding announcement, round closure, or investment update",
        "typical_actions": ["update_deal_record"],
    },
    {
        "route": "action_items",
        "priority": "LOW",
        "description": "Action items, commitments, or deadlines detected in conversation",
        "typical_actions": ["extract_action_items", "append_next_actions"],
    },
    {
        "route": "follow_up",
        "priority": "LOW",
        "description": "Follow-up message or thread continuation with new information",
        "typical_actions": ["update_last_touch"],
    },
]


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


# ── Subcommand: pending ──────────────────────────────────────────────────

def cmd_pending(args):
    """List classified-but-unrouted messages with classification context."""
    conn = get_db()

    query = """
        SELECT m.id, m.source, m.source_id, m.sender, m.subject, m.body,
               m.timestamp, m.attachments, m.channel, m.project_tags,
               cl.matched_slug, cl.match_type, cl.confidence
        FROM messages m
        LEFT JOIN classification_log cl
          ON m.id = cl.source_id
        WHERE m.classified = 1 AND m.routed_at IS NULL
    """
    params = []

    if args.project:
        query += " AND (m.project_tags LIKE ? OR cl.matched_slug = ?)"
        params.extend([f'%"{args.project}"%', args.project])

    query += " ORDER BY m.timestamp DESC LIMIT ?"
    params.append(args.limit)

    rows = conn.execute(query, params).fetchall()

    # Total count
    count_q = """SELECT COUNT(*) as cnt FROM messages
                 WHERE classified = 1 AND routed_at IS NULL"""
    total = conn.execute(count_q).fetchone()["cnt"]

    messages = []
    for r in rows:
        body = r["body"] or ""
        messages.append({
            "id": r["id"],
            "source": r["source"],
            "sender": r["sender"] or "",
            "subject": r["subject"] or "",
            "body_preview": body[:300],
            "timestamp": r["timestamp"] or "",
            "attachments": r["attachments"] or "",
            "channel": r["channel"] or "",
            "matched_slug": r["matched_slug"] or "",
            "match_type": r["match_type"] or "",
            "classification_confidence": r["confidence"],
            "project_tags": r["project_tags"] or "[]",
        })

    print(json.dumps({
        "pending_count": total,
        "showing": len(messages),
        "messages": messages,
    }, indent=2))
    conn.close()


# ── Subcommand: routes ───────────────────────────────────────────────────

def cmd_routes(args):
    """Show available route types and their descriptions."""
    print(json.dumps({
        "routes": ROUTE_DEFINITIONS,
    }, indent=2))


# ── Subcommand: route ────────────────────────────────────────────────────

def cmd_route(args):
    """Store Claude's routing decision for a message."""
    conn = get_db()

    # Parse actions
    try:
        actions = json.loads(args.actions)
    except json.JSONDecodeError:
        actions = [args.actions]

    # Mark as routed
    now = datetime.now().isoformat()
    conn.execute("UPDATE messages SET routed_at = ? WHERE id = ?", (now, args.message_id))
    conn.commit()

    result = {
        "status": "routed",
        "message_id": args.message_id,
        "route": args.route,
        "priority": args.priority,
        "actions": actions,
    }
    if args.reasoning:
        result["reasoning"] = args.reasoning

    print(json.dumps(result, indent=2))
    conn.close()


# ── Subcommand: batch-route ──────────────────────────────────────────────

def cmd_batch_route(args):
    """Store multiple routing decisions at once."""
    conn = get_db()

    try:
        decisions = json.loads(args.decisions)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        return

    now = datetime.now().isoformat()
    routed = 0
    action_plan = []

    for d in decisions:
        try:
            msg_id = d["message_id"]
            conn.execute("UPDATE messages SET routed_at = ? WHERE id = ?", (now, msg_id))

            actions = d.get("actions", [])
            if isinstance(actions, str):
                try:
                    actions = json.loads(actions)
                except json.JSONDecodeError:
                    actions = [actions]

            action_plan.append({
                "message_id": msg_id,
                "route": d.get("route", ""),
                "priority": d.get("priority", "LOW"),
                "actions": actions,
            })
            routed += 1
        except Exception as e:
            print(json.dumps({"warning": f"Error on message {d.get('message_id')}: {e}"}),
                  file=sys.stderr)

    conn.commit()
    print(json.dumps({
        "status": "batch_complete",
        "routed": routed,
        "action_plan": action_plan,
    }, indent=2))
    conn.close()


# ── Subcommand: mark-routed ──────────────────────────────────────────────

def cmd_mark_routed(args):
    """Mark messages as routed without specifying a route (no action needed)."""
    conn = get_db()

    ids = [int(x.strip()) for x in args.message_ids.split(",") if x.strip()]
    now = datetime.now().isoformat()

    marked = 0
    for msg_id in ids:
        conn.execute("UPDATE messages SET routed_at = ? WHERE id = ?", (now, msg_id))
        marked += 1

    conn.commit()
    print(json.dumps({
        "status": "marked_routed",
        "count": marked,
        "message_ids": ids,
    }))
    conn.close()


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="VFT RLM Router CLI — used by Claude Code for reactive message routing",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # pending
    p_pending = subparsers.add_parser("pending", help="List classified-but-unrouted messages")
    p_pending.add_argument("--project", type=str, help="Filter to a specific deal/project slug")
    p_pending.add_argument("--limit", type=int, default=50)

    # routes
    subparsers.add_parser("routes", help="Show available route types")

    # route
    p_route = subparsers.add_parser("route", help="Store a routing decision")
    p_route.add_argument("--message-id", type=int, required=True)
    p_route.add_argument("--route", required=True,
                         choices=["term_sheet", "dataroom", "meeting", "intro",
                                  "funding", "action_items", "follow_up"])
    p_route.add_argument("--priority", required=True,
                         choices=["URGENT", "HIGH", "MEDIUM", "LOW"])
    p_route.add_argument("--actions", required=True, help="JSON array of action strings")
    p_route.add_argument("--reasoning", type=str, help="Claude's reasoning for the route")

    # batch-route
    p_batch = subparsers.add_parser("batch-route", help="Store multiple routing decisions")
    p_batch.add_argument("--decisions", required=True,
                         help='JSON array: [{"message_id": 1, "route": "x", "priority": "HIGH", "actions": [...]}]')

    # mark-routed
    p_mark = subparsers.add_parser("mark-routed", help="Mark messages as needing no action")
    p_mark.add_argument("--message-ids", required=True,
                        help="Comma-separated message IDs")

    args = parser.parse_args()

    if not DB_PATH.exists():
        print(json.dumps({"error": f"Database not found: {DB_PATH}"}))
        sys.exit(1)

    commands = {
        "pending": cmd_pending,
        "routes": cmd_routes,
        "route": cmd_route,
        "batch-route": cmd_batch_route,
        "mark-routed": cmd_mark_routed,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
