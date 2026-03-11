#!/usr/bin/env python3
"""
VFT Ingestion Database — Migration v2: Unified Messages Table

Migrates from schema v1 (separate emails/transcripts tables) to schema v2
(unified messages table) while preserving all existing data.

Usage:
    python migrate_v2_unified_messages.py                  # migrate ingestion.db in same dir
    python migrate_v2_unified_messages.py --db /path/to.db # explicit path
    python migrate_v2_unified_messages.py --dry-run        # preview without changes
"""

import argparse
import json
import os
import sqlite3
from pathlib import Path


SCHEMA_VERSION = 2

MESSAGES_DDL = """
-- ============================================================
-- Unified messages table  (schema v2)
-- ============================================================

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL CHECK (source IN ('outlook', 'slack', 'whatsapp', 'signal', 'granola', 'web')),
    source_id       TEXT NOT NULL,                       -- original dedup key (outlook_id, granola_id, etc.)
    type            TEXT NOT NULL CHECK (type IN ('email', 'message', 'transcript', 'thread', 'document', 'scrape')),
    sender          TEXT,
    recipients      TEXT,                                -- JSON array
    subject         TEXT,
    body            TEXT,                                -- full body or preview
    timestamp       TEXT NOT NULL,                       -- ISO-8601
    channel         TEXT,                                -- inbox, #channel, group-name, direct, url
    attachments     TEXT,                                -- JSON array of {name, path}
    project_tags    TEXT DEFAULT '[]',                   -- JSON array of project/deal slugs
    raw_path        TEXT,                                -- absolute path to saved file
    metadata        TEXT DEFAULT '{}',                   -- JSON for source-specific extras
    classified      INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_source ON messages(source);
CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_classified ON messages(classified);
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel);
"""

# Update classification_log to support unified source references
CLASSIFICATION_LOG_UPDATE = """
-- Allow 'message' as source_type in classification_log
-- SQLite doesn't support ALTER CHECK, so we recreate if needed
"""


def get_db_path(override: str = None) -> str:
    if override:
        return override
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "ingestion.db")


def migrate(db_path: str, dry_run: bool = False) -> dict:
    """Run the v2 migration."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.row_factory = sqlite3.Row

    # Check current schema version
    try:
        row = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
        current_version = int(row["value"]) if row else 1
    except Exception:
        current_version = 1

    if current_version >= SCHEMA_VERSION:
        print(f"[VFT] Database already at schema v{current_version}, skipping migration.")
        conn.close()
        return {"status": "already_current", "version": current_version}

    stats = {"emails_migrated": 0, "transcripts_migrated": 0, "errors": []}

    if dry_run:
        print("[VFT] DRY RUN — no changes will be made")

    # Check if messages table already exists
    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
    ).fetchone()

    if not existing:
        if not dry_run:
            conn.executescript(MESSAGES_DDL)
            print("[VFT] Created unified messages table")
        else:
            print("[VFT] Would create unified messages table")

    # Migrate emails → messages
    try:
        emails = conn.execute("SELECT * FROM emails").fetchall()
        print(f"[VFT] Found {len(emails)} emails to migrate")

        for email in emails:
            # Build recipients as JSON array
            recipients_raw = email["recipients"] or ""
            recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

            # Build attachments as JSON array
            attachments = []
            if email["has_attachments"] and email["attachment_paths"]:
                try:
                    paths = json.loads(email["attachment_paths"])
                    attachments = [{"name": os.path.basename(p), "path": p} for p in paths]
                except (json.JSONDecodeError, TypeError):
                    pass

            # Build metadata with email-specific fields
            metadata = {
                "sender_domain": email["sender_domain"],
                "folder_saved_to": email["folder_saved_to"],
                "original_email_id": email["id"],
            }

            if not dry_run:
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO messages
                           (source, source_id, type, sender, recipients, subject, body,
                            timestamp, channel, attachments, project_tags, raw_path,
                            metadata, classified)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            "outlook",
                            email["outlook_id"] or f"email-{email['id']}",
                            "email",
                            email["sender"],
                            json.dumps(recipients),
                            email["subject"],
                            email["body_preview"],
                            email["date"],
                            "inbox",
                            json.dumps(attachments),
                            "[]",  # project_tags — will be populated by classifier
                            email["raw_path"],
                            json.dumps(metadata),
                            email["classified"],
                        ),
                    )
                    stats["emails_migrated"] += 1
                except sqlite3.IntegrityError as e:
                    stats["errors"].append(f"Email {email['id']}: {e}")
            else:
                stats["emails_migrated"] += 1

    except Exception as e:
        stats["errors"].append(f"Email migration error: {e}")

    # Migrate transcripts → messages
    try:
        transcripts = conn.execute("SELECT * FROM transcripts").fetchall()
        print(f"[VFT] Found {len(transcripts)} transcripts to migrate")

        for transcript in transcripts:
            # Participants as recipients
            participants_raw = transcript["participants"] or ""
            participants = [p.strip() for p in participants_raw.split(",") if p.strip()]

            metadata = {
                "original_transcript_id": transcript["id"],
            }

            if not dry_run:
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO messages
                           (source, source_id, type, sender, recipients, subject, body,
                            timestamp, channel, attachments, project_tags, raw_path,
                            metadata, classified)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            "granola",
                            transcript["granola_id"] or f"transcript-{transcript['id']}",
                            "transcript",
                            None,  # transcripts don't have a single sender
                            json.dumps(participants),
                            transcript["title"],
                            transcript["summary"],
                            transcript["date"],
                            "meeting",
                            "[]",
                            "[]",
                            transcript["raw_path"],
                            json.dumps(metadata),
                            transcript["classified"],
                        ),
                    )
                    stats["transcripts_migrated"] += 1
                except sqlite3.IntegrityError as e:
                    stats["errors"].append(f"Transcript {transcript['id']}: {e}")
            else:
                stats["transcripts_migrated"] += 1

    except Exception as e:
        stats["errors"].append(f"Transcript migration error: {e}")

    # Recreate classification_log with expanded source_type check
    # (keep existing data, just allow 'message' as a new source_type)
    if not dry_run:
        # Check if classification_log needs updating
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS classification_log_v2 (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type     TEXT NOT NULL CHECK (source_type IN ('email', 'transcript', 'message')),
                    source_id       INTEGER NOT NULL,
                    matched_slug    TEXT,
                    match_type      TEXT CHECK (match_type IN ('deal', 'project', 'new_deal', 'new_project', 'unclassified')),
                    confidence      REAL DEFAULT 0.0,
                    rule_hits       TEXT,
                    auto_created    INTEGER DEFAULT 0,
                    reviewed        INTEGER DEFAULT 0,
                    created_at      TEXT DEFAULT (datetime('now'))
                )"""
            )
            # Copy existing data
            conn.execute(
                "INSERT OR IGNORE INTO classification_log_v2 SELECT * FROM classification_log"
            )
            conn.execute("DROP TABLE IF EXISTS classification_log")
            conn.execute("ALTER TABLE classification_log_v2 RENAME TO classification_log")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_classification_log_source ON classification_log(source_type, source_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_classification_log_slug ON classification_log(matched_slug)"
            )
        except Exception as e:
            stats["errors"].append(f"Classification log migration: {e}")

        # Update processed_items to support 'message' source_type
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS processed_items_v2 (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type     TEXT NOT NULL CHECK (source_type IN ('email', 'transcript', 'message')),
                    source_id       INTEGER NOT NULL,
                    action_taken    TEXT,
                    timestamp       TEXT DEFAULT (datetime('now')),
                    UNIQUE(source_type, source_id, action_taken)
                )"""
            )
            conn.execute(
                "INSERT OR IGNORE INTO processed_items_v2 SELECT * FROM processed_items"
            )
            conn.execute("DROP TABLE IF EXISTS processed_items")
            conn.execute("ALTER TABLE processed_items_v2 RENAME TO processed_items")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_processed_items_source ON processed_items(source_type, source_id)"
            )
        except Exception as e:
            stats["errors"].append(f"Processed items migration: {e}")

        # Update schema version
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        conn.commit()

    stats["status"] = "migrated" if not dry_run else "dry_run"
    stats["version"] = SCHEMA_VERSION

    conn.close()
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate VFT database to schema v2")
    parser.add_argument("--db", type=str, help="Path to database file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    args = parser.parse_args()

    db_path = get_db_path(args.db)
    print(f"[VFT] Migrating {db_path} to schema v{SCHEMA_VERSION}")

    stats = migrate(db_path, dry_run=args.dry_run)

    print(f"\n[VFT] Migration results:")
    print(f"  Status: {stats['status']}")
    print(f"  Schema version: {stats['version']}")
    print(f"  Emails migrated: {stats.get('emails_migrated', 0)}")
    print(f"  Transcripts migrated: {stats.get('transcripts_migrated', 0)}")
    if stats.get("errors"):
        print(f"  Errors ({len(stats['errors'])}):")
        for err in stats["errors"]:
            print(f"    - {err}")
