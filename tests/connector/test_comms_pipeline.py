"""
Connector-level tests for the Communications Scanning pipeline.

Tests the full flow: messages → classify → route across multiple sources.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path("/Users/nebnoseflow/due_diligences")
if not (REPO_ROOT / "fund" / "metadata" / "init_db.py").exists():
    REPO_ROOT = _WORKTREE_ROOT
sys.path.insert(0, str(REPO_ROOT / "fund" / "metadata"))

from conftest import run_cli, parse_json_output

CLASSIFY_SCRIPT = REPO_ROOT / "skills" / "deal-project-classifier" / "scripts" / "classify_messages.py"
ROUTE_SCRIPT = REPO_ROOT / "skills" / "reactive-router" / "scripts" / "route_messages.py"


class TestCommsPipeline:

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.root = tmp_path
        db_dir = tmp_path / "fund" / "metadata" / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "fund" / "crm").mkdir(parents=True, exist_ok=True)
        (tmp_path / "projects").mkdir(parents=True, exist_ok=True)

        from init_db import init_db
        self.db_path = str(db_dir / "ingestion.db")
        self.conn = init_db(self.db_path)

        # Note: classify_messages.py expects flat array (known format mismatch bug)
        (tmp_path / "fund" / "crm" / "deals.json").write_text(json.dumps([
            {"slug": "midbound", "company_name": "Midbound", "status": "active",
             "domains": ["midbound.com"], "contact_emails": ["ceo@midbound.com"]},
        ]))
        (tmp_path / "projects" / "projects.json").write_text(json.dumps([
            {"slug": "fund-ops", "project_name": "Fund Ops", "status": "active"},
        ]))

        self.env = {"VFT_REPO_ROOT": str(tmp_path)}

    def _insert_msgs(self, source, count, **overrides):
        ids = []
        for i in range(count):
            cursor = self.conn.execute(
                """INSERT INTO messages
                   (source, source_id, type, sender, subject, body, timestamp,
                    channel, attachments, project_tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source, f"{source}-{i}-{datetime.now().timestamp()}",
                 overrides.get("type", "email" if source == "outlook" else "message"),
                 overrides.get("sender", f"user{i}@{source}.com"),
                 overrides.get("subject", f"Test {source} {i}"),
                 overrides.get("body", f"Body from {source} {i}"),
                 (datetime.now() - timedelta(hours=i)).isoformat(),
                 overrides.get("channel", "inbox"),
                 "[]", "[]"),
            )
            ids.append(cursor.lastrowid)
        self.conn.commit()
        return ids

    def test_full_pipeline_classify_then_route(self):
        """Insert → classify → route → verify full chain."""
        ids = self._insert_msgs("outlook", 5, sender="ceo@midbound.com")

        # Classify all
        decisions = [{"message_id": i, "slug": "midbound", "match_type": "deal"} for i in ids]
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "batch-classify", "--decisions", json.dumps(decisions),
        ], self.env)
        data = parse_json_output(out)
        assert data["classified"] == 5

        # Route all
        route_decisions = [
            {"message_id": i, "route": "follow_up", "priority": "LOW", "actions": ["update"]}
            for i in ids
        ]
        rc, out, _ = run_cli(ROUTE_SCRIPT, [
            "batch-route", "--decisions", json.dumps(route_decisions),
        ], self.env)
        data = parse_json_output(out)
        assert data["routed"] == 5

        # Verify nothing pending
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        assert parse_json_output(out)["pending_count"] == 0

        rc, out, _ = run_cli(ROUTE_SCRIPT, ["pending"], self.env)
        assert parse_json_output(out)["pending_count"] == 0

    def test_multi_source_batch(self):
        """Messages from 3 different sources all classifiable."""
        outlook_ids = self._insert_msgs("outlook", 5)
        slack_ids = self._insert_msgs("slack", 3)
        signal_ids = self._insert_msgs("signal", 2)
        all_ids = outlook_ids + slack_ids + signal_ids

        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        data = parse_json_output(out)
        assert data["pending_count"] == 10

        # Classify all to midbound
        decisions = [{"message_id": i, "slug": "midbound", "match_type": "deal"} for i in all_ids]
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "batch-classify", "--decisions", json.dumps(decisions),
        ], self.env)
        data = parse_json_output(out)
        assert data["classified"] == 10

    def test_duplicate_message_dedup(self):
        """Duplicate (source, source_id) should be rejected by DB."""
        self.conn.execute(
            """INSERT INTO messages
               (source, source_id, type, sender, subject, body, timestamp, channel, attachments, project_tags)
               VALUES ('outlook', 'dup-001', 'email', 'a@b.com', 'Test', 'Body',
                       '2026-03-10T10:00:00', 'inbox', '[]', '[]')""")
        self.conn.commit()

        import sqlite3
        with pytest.raises(sqlite3.IntegrityError):
            self.conn.execute(
                """INSERT INTO messages
                   (source, source_id, type, sender, subject, body, timestamp, channel, attachments, project_tags)
                   VALUES ('outlook', 'dup-001', 'email', 'b@c.com', 'Other', 'Other',
                           '2026-03-10T11:00:00', 'inbox', '[]', '[]')""")

    def test_empty_pipeline(self):
        """No messages → no errors, counts all zero."""
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        assert parse_json_output(out)["pending_count"] == 0

        rc, out, _ = run_cli(ROUTE_SCRIPT, ["pending"], self.env)
        assert parse_json_output(out)["pending_count"] == 0

    def test_thread_grouping(self):
        """3 messages with same sender classified to same deal."""
        ids = self._insert_msgs("outlook", 3, sender="ceo@midbound.com",
                                subject="Re: Midbound Update")

        decisions = [
            {"message_id": i, "slug": "midbound", "match_type": "deal", "confidence": 0.95}
            for i in ids
        ]
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "batch-classify", "--decisions", json.dumps(decisions),
        ], self.env)
        assert parse_json_output(out)["classified"] == 3

        # All should have midbound in project_tags
        for mid in ids:
            row = self.conn.execute("SELECT project_tags FROM messages WHERE id=?", (mid,)).fetchone()
            tags = json.loads(row[0])
            assert "midbound" in tags

    def test_large_batch_200_messages(self):
        """200 messages pipeline without OOM."""
        ids = self._insert_msgs("outlook", 200)
        decisions = [{"message_id": i, "slug": "midbound", "match_type": "deal"} for i in ids]
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "batch-classify", "--decisions", json.dumps(decisions),
        ], self.env)
        assert rc == 0
        assert parse_json_output(out)["classified"] == 200

    def test_attachment_metadata_preserved(self):
        """Message with attachment metadata preserved through pipeline."""
        attachments = json.dumps([
            {"name": "dataroom.zip", "path": "/tmp/dataroom.zip", "size": 1024000}
        ])
        cursor = self.conn.execute(
            """INSERT INTO messages
               (source, source_id, type, sender, subject, body, timestamp,
                channel, attachments, project_tags)
               VALUES ('outlook', 'attach-001', 'email', 'a@b.com',
                       'Dataroom', 'Attached', '2026-03-10T10:00:00',
                       'inbox', ?, '[]')""",
            (attachments,),
        )
        self.conn.commit()
        msg_id = cursor.lastrowid

        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        data = parse_json_output(out)
        msg = data["messages"][0]
        att = json.loads(msg["attachments"]) if isinstance(msg["attachments"], str) else msg["attachments"]
        assert len(att) > 0 or "dataroom" in msg["attachments"]
