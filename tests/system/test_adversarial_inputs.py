"""
System-level adversarial tests.

Tests SQL injection, Unicode edge cases, empty states, corrupted data,
boundary values, and malformed JSON across the entire system.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path("/Users/nebnoseflow/due_diligences")
if not (REPO_ROOT / "fund" / "metadata" / "init_db.py").exists():
    REPO_ROOT = _WORKTREE_ROOT
sys.path.insert(0, str(REPO_ROOT / "fund" / "metadata"))

from conftest import (
    run_cli, parse_json_output,
    UNICODE_NAMES, SQL_INJECTIONS, MALFORMED_EMAILS, BOUNDARY_VALUES,
)

CLASSIFY_SCRIPT = REPO_ROOT / "skills" / "deal-project-classifier" / "scripts" / "classify_messages.py"
ROUTE_SCRIPT = REPO_ROOT / "skills" / "reactive-router" / "scripts" / "route_messages.py"


class TestSQLInjection:
    """SQL injection attempts in every text field."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        db_dir = tmp_path / "fund" / "metadata" / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "fund" / "crm").mkdir(parents=True, exist_ok=True)
        (tmp_path / "projects").mkdir(parents=True, exist_ok=True)

        from init_db import init_db
        self.db_path = str(db_dir / "ingestion.db")
        self.conn = init_db(self.db_path)

        (tmp_path / "fund" / "crm" / "deals.json").write_text('[]')
        (tmp_path / "projects" / "projects.json").write_text('[]')
        self.env = {"VFT_REPO_ROOT": str(tmp_path)}

    def _insert_msg(self, sender="a@b.com", subject="Test", body="Body"):
        cursor = self.conn.execute(
            """INSERT INTO messages
               (source, source_id, type, sender, subject, body, timestamp,
                channel, attachments, project_tags)
               VALUES ('outlook', ?, 'email', ?, ?, ?, ?, 'inbox', '[]', '[]')""",
            (f"inj-{datetime.now().timestamp()}", sender, subject, body,
             datetime.now().isoformat()),
        )
        self.conn.commit()
        return cursor.lastrowid

    @pytest.mark.parametrize("injection", SQL_INJECTIONS)
    def test_sql_injection_in_slug(self, injection):
        """SQL injection in --slug is safely parameterized."""
        msg_id = self._insert_msg()
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "classify", "--message-id", str(msg_id),
            "--slug", injection, "--match-type", "deal",
        ], self.env)
        # Should not crash — value stored safely
        assert rc == 0
        # Verify messages table still exists
        count = self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        assert count >= 1

    @pytest.mark.parametrize("injection", SQL_INJECTIONS)
    def test_sql_injection_in_reasoning(self, injection):
        """SQL injection in reasoning JSON."""
        msg_id = self._insert_msg()
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "classify", "--message-id", str(msg_id),
            "--slug", "test", "--match-type", "deal",
            "--reasoning", injection,
        ], self.env)
        assert rc == 0

    @pytest.mark.parametrize("injection", SQL_INJECTIONS)
    def test_sql_injection_in_sender(self, injection):
        """SQL injection in message sender field."""
        msg_id = self._insert_msg(sender=injection)
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        assert rc == 0
        data = parse_json_output(out)
        assert data["pending_count"] >= 1

    @pytest.mark.parametrize("injection", SQL_INJECTIONS)
    def test_sql_injection_in_subject(self, injection):
        msg_id = self._insert_msg(subject=injection)
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        assert rc == 0


class TestUnicodeBomb:
    """Unicode edge cases across the pipeline."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        db_dir = tmp_path / "fund" / "metadata" / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "fund" / "crm").mkdir(parents=True, exist_ok=True)
        (tmp_path / "projects").mkdir(parents=True, exist_ok=True)

        from init_db import init_db
        self.db_path = str(db_dir / "ingestion.db")
        self.conn = init_db(self.db_path)

        (tmp_path / "fund" / "crm" / "deals.json").write_text('[]')
        (tmp_path / "projects" / "projects.json").write_text('[]')
        self.env = {"VFT_REPO_ROOT": str(tmp_path)}

    @pytest.mark.parametrize("name", UNICODE_NAMES)
    def test_unicode_company_create(self, name):
        """Auto-create deal with unicode name."""
        cursor = self.conn.execute(
            """INSERT INTO messages
               (source, source_id, type, sender, subject, body, timestamp,
                channel, attachments, project_tags)
               VALUES ('outlook', ?, 'email', 'a@b.com', ?, 'Body', ?, 'inbox', '[]', '[]')""",
            (f"uni-{datetime.now().timestamp()}", name, datetime.now().isoformat()),
        )
        self.conn.commit()
        msg_id = cursor.lastrowid

        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "auto-create", "--type", "deal", "--name", name,
            "--message-id", str(msg_id),
        ], self.env)
        assert rc == 0

    def test_unicode_in_message_body(self):
        """Unicode in body text: RTL, zero-width, combining chars, emoji."""
        body = "Hello \u200b\u200c\u200d World \u0644\u0627 \u0300\u0301 \U0001F600 \U0001F680"
        cursor = self.conn.execute(
            """INSERT INTO messages
               (source, source_id, type, sender, subject, body, timestamp,
                channel, attachments, project_tags)
               VALUES ('outlook', ?, 'email', 'a@b.com', 'Unicode Test', ?, ?, 'inbox', '[]', '[]')""",
            (f"uni-body-{datetime.now().timestamp()}", body, datetime.now().isoformat()),
        )
        self.conn.commit()
        msg_id = cursor.lastrowid

        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        assert rc == 0
        data = parse_json_output(out)
        assert data["pending_count"] >= 1


class TestEmptyEverything:
    """Empty DB + empty JSON + all commands → no crashes."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        db_dir = tmp_path / "fund" / "metadata" / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "fund" / "crm").mkdir(parents=True, exist_ok=True)
        (tmp_path / "projects").mkdir(parents=True, exist_ok=True)

        from init_db import init_db
        self.db_path = str(db_dir / "ingestion.db")
        self.conn = init_db(self.db_path)

        (tmp_path / "fund" / "crm" / "deals.json").write_text('[]')
        (tmp_path / "projects" / "projects.json").write_text('[]')
        self.env = {"VFT_REPO_ROOT": str(tmp_path)}

    def test_classify_pending_empty(self):
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        assert rc == 0
        assert parse_json_output(out)["pending_count"] == 0

    def test_classify_context_empty(self):
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["context", "--no-rebuild-index"], self.env)
        assert rc == 0
        data = parse_json_output(out)
        assert data["deals_count"] == 0
        assert data["projects_count"] == 0

    def test_route_pending_empty(self):
        rc, out, _ = run_cli(ROUTE_SCRIPT, ["pending"], self.env)
        assert rc == 0
        assert parse_json_output(out)["pending_count"] == 0

    def test_route_routes_always_available(self):
        rc, out, _ = run_cli(ROUTE_SCRIPT, ["routes"], self.env)
        assert rc == 0
        assert len(parse_json_output(out)["routes"]) == 7

    def test_batch_classify_empty_array(self):
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "batch-classify", "--decisions", "[]",
        ], self.env)
        assert rc == 0
        assert parse_json_output(out)["classified"] == 0

    def test_batch_route_empty_array(self):
        rc, out, _ = run_cli(ROUTE_SCRIPT, [
            "batch-route", "--decisions", "[]",
        ], self.env)
        assert rc == 0
        assert parse_json_output(out)["routed"] == 0


class TestCorruptedState:
    """System recovery from corrupted JSON and DB state."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        db_dir = tmp_path / "fund" / "metadata" / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "fund" / "crm").mkdir(parents=True, exist_ok=True)
        (tmp_path / "projects").mkdir(parents=True, exist_ok=True)

        from init_db import init_db
        self.db_path = str(db_dir / "ingestion.db")
        self.conn = init_db(self.db_path)
        self.env = {"VFT_REPO_ROOT": str(tmp_path)}
        self.root = tmp_path

    def test_corrupted_deals_json_context(self):
        """Corrupted deals.json → context still returns (maybe with warning)."""
        (self.root / "fund" / "crm" / "deals.json").write_text("{{invalid json")
        (self.root / "projects" / "projects.json").write_text('[]')

        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["context", "--no-rebuild-index"], self.env)
        # Should not crash
        assert rc == 0

    def test_missing_deals_json_auto_create(self):
        """Missing deals.json → auto-create creates it."""
        # Don't write deals.json at all
        (self.root / "projects" / "projects.json").write_text('[]')

        self.conn.execute(
            """INSERT INTO messages
               (source, source_id, type, sender, subject, body, timestamp,
                channel, attachments, project_tags)
               VALUES ('outlook', 'test-1', 'email', 'a@b.com', 'Test', 'Body',
                       '2026-03-10T10:00:00', 'inbox', '[]', '[]')""")
        self.conn.commit()

        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "auto-create", "--type", "deal", "--name", "NewCo",
            "--message-id", "1",
        ], self.env)
        assert rc == 0
        assert (self.root / "fund" / "crm" / "deals.json").exists()

    def test_corrupted_json_auto_create_recovers(self):
        """Corrupted deals.json → auto-create starts fresh."""
        (self.root / "fund" / "crm" / "deals.json").write_text("not-json")
        (self.root / "projects" / "projects.json").write_text('[]')

        self.conn.execute(
            """INSERT INTO messages
               (source, source_id, type, sender, subject, body, timestamp,
                channel, attachments, project_tags)
               VALUES ('outlook', 'test-2', 'email', 'a@b.com', 'Test', 'Body',
                       '2026-03-10T10:00:00', 'inbox', '[]', '[]')""")
        self.conn.commit()

        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "auto-create", "--type", "deal", "--name", "RecoverCo",
            "--message-id", "1",
        ], self.env)
        assert rc == 0


class TestBoundaryValues:
    """Extreme values across the system."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        db_dir = tmp_path / "fund" / "metadata" / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "fund" / "crm").mkdir(parents=True, exist_ok=True)
        (tmp_path / "projects").mkdir(parents=True, exist_ok=True)

        from init_db import init_db
        self.db_path = str(db_dir / "ingestion.db")
        self.conn = init_db(self.db_path)

        (tmp_path / "fund" / "crm" / "deals.json").write_text('[]')
        (tmp_path / "projects" / "projects.json").write_text('[]')
        self.env = {"VFT_REPO_ROOT": str(tmp_path)}

    def _insert_msg(self, **kwargs):
        defaults = {
            "source": "outlook", "source_id": f"bnd-{datetime.now().timestamp()}",
            "type": "email", "sender": "a@b.com", "subject": "Test",
            "body": "Body", "timestamp": datetime.now().isoformat(),
        }
        defaults.update(kwargs)
        cursor = self.conn.execute(
            """INSERT INTO messages
               (source, source_id, type, sender, subject, body, timestamp,
                channel, attachments, project_tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'inbox', '[]', '[]')""",
            (defaults["source"], defaults["source_id"], defaults["type"],
             defaults["sender"], defaults["subject"], defaults["body"],
             defaults["timestamp"]),
        )
        self.conn.commit()
        return cursor.lastrowid

    @pytest.mark.parametrize("confidence", BOUNDARY_VALUES["confidence"])
    def test_confidence_boundaries(self, confidence):
        msg_id = self._insert_msg()
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "classify", "--message-id", str(msg_id),
            "--slug", "test", "--match-type", "deal",
            "--confidence", str(confidence),
        ], self.env)
        assert rc == 0

    def test_100kb_body(self):
        """100KB message body."""
        msg_id = self._insert_msg(body="x" * 100_000)
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        assert rc == 0
        data = parse_json_output(out)
        # body_preview should be 300 chars
        assert len(data["messages"][0]["body_preview"]) == 300

    def test_empty_body(self):
        msg_id = self._insert_msg(body="")
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        assert rc == 0

    def test_empty_subject(self):
        msg_id = self._insert_msg(subject="")
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        assert rc == 0


class TestMalformedJSON:
    """Malformed JSON in every field that accepts JSON."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        db_dir = tmp_path / "fund" / "metadata" / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "fund" / "crm").mkdir(parents=True, exist_ok=True)
        (tmp_path / "projects").mkdir(parents=True, exist_ok=True)

        from init_db import init_db
        self.db_path = str(db_dir / "ingestion.db")
        self.conn = init_db(self.db_path)

        (tmp_path / "fund" / "crm" / "deals.json").write_text('[]')
        (tmp_path / "projects" / "projects.json").write_text('[]')
        self.env = {"VFT_REPO_ROOT": str(tmp_path)}

    def test_malformed_batch_classify_json(self):
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "batch-classify", "--decisions", "not valid json at all",
        ], self.env)
        assert rc == 0  # error returned as JSON, not crash
        data = parse_json_output(out)
        assert "error" in data

    def test_malformed_batch_route_json(self):
        rc, out, _ = run_cli(ROUTE_SCRIPT, [
            "batch-route", "--decisions", "{broken",
        ], self.env)
        assert rc == 0
        data = parse_json_output(out)
        assert "error" in data

    def test_malformed_reasoning_becomes_note(self):
        """Non-JSON reasoning wrapped in {"note": ...}."""
        self.conn.execute(
            """INSERT INTO messages
               (source, source_id, type, sender, subject, body, timestamp,
                channel, attachments, project_tags)
               VALUES ('outlook', 'mal-001', 'email', 'a@b.com', 'Test', 'Body',
                       '2026-03-10T10:00:00', 'inbox', '[]', '[]')""")
        self.conn.commit()

        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "classify", "--message-id", "1",
            "--slug", "test", "--match-type", "deal",
            "--reasoning", "just a plain string not json",
        ], self.env)
        assert rc == 0

        # Verify it was stored
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT rule_hits FROM classification_log WHERE source_id=1").fetchone()
        stored = json.loads(row[0])
        assert "note" in stored
        conn.close()
