#!/usr/bin/env python3
"""
VFT Message Ingestion — Unified Message Inserter

Inserts or updates a single message in the unified messages table.
Handles dedup, validation, and schema conformance.

Usage:
    python ingest_message.py --source outlook --source-id "abc123" --type email --payload '{"sender": "...", ...}'
    python ingest_message.py --from-file /path/to/message.json
    python ingest_message.py --dry-run --payload '...'
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"

VALID_SOURCES = {"outlook", "slack", "whatsapp", "signal", "granola", "web"}
VALID_TYPES = {"email", "message", "transcript", "thread", "document", "scrape"}


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.row_factory = sqlite3.Row
    return conn


def validate_message(msg: dict) -> list:
    """Validate a message payload. Returns list of errors (empty = valid)."""
    errors = []
    if msg.get("source") not in VALID_SOURCES:
        errors.append(f"Invalid source: {msg.get('source')}. Must be one of {VALID_SOURCES}")
    if msg.get("type") not in VALID_TYPES:
        errors.append(f"Invalid type: {msg.get('type')}. Must be one of {VALID_TYPES}")
    if not msg.get("source_id"):
        errors.append("source_id is required")
    if not msg.get("timestamp"):
        errors.append("timestamp is required")
    return errors


def ingest_message(msg: dict, dry_run: bool = False) -> dict:
    """Insert a message into the unified messages table.

    Returns dict with status and message_id.
    """
    errors = validate_message(msg)
    if errors:
        return {"status": "error", "errors": errors}

    if dry_run:
        return {"status": "dry_run", "message": msg}

    conn = get_db()

    # Ensure messages table exists
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    if "messages" not in tables:
        print("[VFT] Messages table not found. Run migrate_v2_unified_messages.py first.")
        conn.close()
        return {"status": "error", "errors": ["messages table not found — run migration"]}

    try:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO messages
               (source, source_id, type, sender, recipients, subject, body,
                timestamp, channel, attachments, project_tags, raw_path,
                metadata, classified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                msg["source"],
                msg["source_id"],
                msg["type"],
                msg.get("sender"),
                json.dumps(msg.get("recipients", [])),
                msg.get("subject"),
                msg.get("body"),
                msg["timestamp"],
                msg.get("channel"),
                json.dumps(msg.get("attachments", [])),
                json.dumps(msg.get("project_tags", [])),
                msg.get("raw_path"),
                json.dumps(msg.get("metadata", {})),
                0,
            ),
        )
        conn.commit()

        if cursor.rowcount == 0:
            # Duplicate — already exists
            existing = conn.execute(
                "SELECT id FROM messages WHERE source = ? AND source_id = ?",
                (msg["source"], msg["source_id"]),
            ).fetchone()
            conn.close()
            return {
                "status": "duplicate",
                "message_id": existing["id"] if existing else None,
            }

        message_id = cursor.lastrowid
        conn.close()
        return {"status": "inserted", "message_id": message_id}

    except Exception as e:
        conn.close()
        return {"status": "error", "errors": [str(e)]}


def ingest_batch(messages: list, dry_run: bool = False) -> dict:
    """Insert multiple messages. Returns summary."""
    results = {"inserted": 0, "duplicates": 0, "errors": 0, "details": []}
    for msg in messages:
        result = ingest_message(msg, dry_run=dry_run)
        results["details"].append(result)
        if result["status"] == "inserted":
            results["inserted"] += 1
        elif result["status"] == "duplicate":
            results["duplicates"] += 1
        else:
            results["errors"] += 1
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Message Ingestion")
    parser.add_argument("--source", type=str, help="Message source")
    parser.add_argument("--source-id", type=str, help="Source dedup key")
    parser.add_argument("--type", type=str, dest="msg_type", help="Message type")
    parser.add_argument("--payload", type=str, help="Full message as JSON string")
    parser.add_argument("--from-file", type=str, help="Load message from JSON file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.from_file:
        with open(args.from_file) as f:
            msg = json.load(f)
    elif args.payload:
        msg = json.loads(args.payload)
    else:
        # Build from individual args
        msg = {
            "source": args.source,
            "source_id": args.source_id,
            "type": args.msg_type,
        }
        # Read remaining fields from stdin if available
        if not sys.stdin.isatty():
            extra = json.load(sys.stdin)
            msg.update(extra)

    result = ingest_message(msg, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
