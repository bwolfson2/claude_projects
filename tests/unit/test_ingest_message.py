#!/usr/bin/env python3
"""Unit tests for skills/message-ingestion/scripts/ingest_message.py"""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path("/Users/nebnoseflow/due_diligences")
if not REPO_ROOT.exists():
    REPO_ROOT = Path(__file__).resolve().parents[4]

SCRIPT_DIR = REPO_ROOT / "skills" / "message-ingestion" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import ingest_message  # noqa: E402

MSG_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL CHECK(source IN ('outlook','slack','whatsapp','signal','granola','web')),
    source_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('email','message','transcript','thread','document','scrape')),
    sender TEXT, recipients TEXT, subject TEXT, body TEXT,
    timestamp TEXT, channel TEXT, attachments TEXT DEFAULT '[]',
    project_tags TEXT DEFAULT '[]', raw_path TEXT, metadata TEXT DEFAULT '{}',
    classified INTEGER DEFAULT 0, routed_at TEXT, created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source, source_id)
);
"""


def _make_msg(**overrides):
    """Return a minimal valid message dict with optional overrides."""
    base = {
        "source": "outlook",
        "source_id": "msg-001",
        "type": "email",
        "sender": "alice@example.com",
        "recipients": ["bob@example.com"],
        "subject": "Test",
        "body": "Hello world",
        "timestamp": "2025-01-15T10:00:00Z",
    }
    base.update(overrides)
    return base


@pytest.fixture
def db(tmp_path):
    """Create a temp DB with the messages table and patch ingest_message.get_db."""
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.executescript(MSG_SCHEMA)
    conn.commit()

    def _get_db():
        c = sqlite3.connect(str(db_file))
        c.execute("PRAGMA journal_mode=OFF")
        c.row_factory = sqlite3.Row
        return c

    with patch.object(ingest_message, "get_db", _get_db):
        yield conn
    conn.close()


# ── validate_message tests ─────────────────────────────────────────────


class TestValidateMessage:
    def test_valid_message(self):
        errors = ingest_message.validate_message(_make_msg())
        assert errors == []

    def test_missing_source(self):
        msg = _make_msg()
        del msg["source"]
        errors = ingest_message.validate_message(msg)
        assert any("source" in e.lower() for e in errors)

    def test_invalid_source(self):
        errors = ingest_message.validate_message(_make_msg(source="twitter"))
        assert any("source" in e.lower() for e in errors)

    def test_invalid_type(self):
        errors = ingest_message.validate_message(_make_msg(type="podcast"))
        assert any("type" in e.lower() for e in errors)


# ── ingest_message tests ──────────────────────────────────────────────


class TestIngestMessage:
    def test_insert(self, db):
        result = ingest_message.ingest_message(_make_msg())
        assert result["status"] == "inserted"
        assert isinstance(result["message_id"], int)

    def test_duplicate(self, db):
        msg = _make_msg()
        r1 = ingest_message.ingest_message(msg)
        assert r1["status"] == "inserted"
        r2 = ingest_message.ingest_message(msg)
        assert r2["status"] == "duplicate"
        assert r2["message_id"] == r1["message_id"]

    def test_dry_run(self, db):
        result = ingest_message.ingest_message(_make_msg(), dry_run=True)
        assert result["status"] == "dry_run"
        # Nothing in DB
        row = db.execute("SELECT count(*) as cnt FROM messages").fetchone()
        assert row["cnt"] == 0

    def test_sql_injection(self, db):
        msg = _make_msg(
            source_id="inj-1",
            body="'; DROP TABLE messages; --",
            subject="Robert'); DROP TABLE messages;--",
        )
        result = ingest_message.ingest_message(msg)
        assert result["status"] == "inserted"
        # Table still intact
        row = db.execute("SELECT count(*) as cnt FROM messages").fetchone()
        assert row["cnt"] == 1

    def test_unicode_all_fields(self, db):
        msg = _make_msg(
            source_id="uni-1",
            sender="taro@example.jp",
            subject="Konnichiwa",
            body="This body has emojis and CJK characters",
            channel="#general",
        )
        result = ingest_message.ingest_message(msg)
        assert result["status"] == "inserted"
        row = db.execute(
            "SELECT body FROM messages WHERE id = ?", (result["message_id"],)
        ).fetchone()
        assert "CJK" in row["body"]

    def test_malformed_json_fields(self, db):
        """recipients and attachments that are not lists should still be stored."""
        msg = _make_msg(
            source_id="mal-1",
            recipients="not-a-list",
            attachments="also-not-a-list",
        )
        result = ingest_message.ingest_message(msg)
        assert result["status"] == "inserted"


# ── ingest_batch tests ────────────────────────────────────────────────


class TestIngestBatch:
    def test_batch_insert(self, db):
        messages = [_make_msg(source_id=f"batch-{i}") for i in range(5)]
        result = ingest_message.ingest_batch(messages)
        assert result["inserted"] == 5
        assert result["duplicates"] == 0
        assert result["errors"] == 0

    def test_batch_with_duplicates(self, db):
        messages = [
            _make_msg(source_id="dup-1"),
            _make_msg(source_id="dup-2"),
            _make_msg(source_id="dup-1"),  # duplicate
        ]
        result = ingest_message.ingest_batch(messages)
        assert result["inserted"] == 2
        assert result["duplicates"] == 1
