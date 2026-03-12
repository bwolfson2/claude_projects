"""
Connector-level tests for the Reactive Automation pipeline.

Tests: classify → route → verify action plans for different message types.
"""

import json
import os
import sys
from datetime import datetime
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


class TestReactiveAutomation:

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        db_dir = tmp_path / "fund" / "metadata" / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "fund" / "crm").mkdir(parents=True, exist_ok=True)
        (tmp_path / "projects").mkdir(parents=True, exist_ok=True)

        from init_db import init_db
        self.db_path = str(db_dir / "ingestion.db")
        self.conn = init_db(self.db_path)

        # Note: classify_messages.py expects flat array (known format mismatch bug)
        (tmp_path / "fund" / "crm" / "deals.json").write_text(json.dumps([
            {"slug": "acme", "company_name": "Acme Corp", "status": "active"},
        ]))
        (tmp_path / "projects" / "projects.json").write_text('[]')

        self.env = {"VFT_REPO_ROOT": str(tmp_path)}

    def _insert_and_classify(self, sender, subject, body, slug="acme"):
        cursor = self.conn.execute(
            """INSERT INTO messages
               (source, source_id, type, sender, subject, body, timestamp,
                channel, attachments, project_tags)
               VALUES ('outlook', ?, 'email', ?, ?, ?, ?, 'inbox', '[]', '[]')""",
            (f"msg-{datetime.now().timestamp()}", sender, subject, body,
             datetime.now().isoformat()),
        )
        self.conn.commit()
        msg_id = cursor.lastrowid

        run_cli(CLASSIFY_SCRIPT, [
            "classify", "--message-id", str(msg_id),
            "--slug", slug, "--match-type", "deal",
        ], self.env)
        return msg_id

    def test_dataroom_email_routed_high(self):
        msg_id = self._insert_and_classify(
            "ceo@acme.com", "Acme Dataroom Access",
            "Here's the dataroom link with all diligence materials.")

        rc, out, _ = run_cli(ROUTE_SCRIPT, [
            "route", "--message-id", str(msg_id),
            "--route", "dataroom", "--priority", "HIGH",
            "--actions", '["download_attachments", "run_dataroom_intake"]',
        ], self.env)
        assert rc == 0
        data = parse_json_output(out)
        assert data["route"] == "dataroom"
        assert data["priority"] == "HIGH"

    def test_term_sheet_routed_urgent(self):
        msg_id = self._insert_and_classify(
            "legal@acme.com", "Term Sheet - Acme Corp Series A",
            "Please find attached the term sheet for your review.")

        rc, out, _ = run_cli(ROUTE_SCRIPT, [
            "route", "--message-id", str(msg_id),
            "--route", "term_sheet", "--priority", "URGENT",
            "--actions", '["flag_urgent", "save_to_diligence"]',
        ], self.env)
        data = parse_json_output(out)
        assert data["route"] == "term_sheet"
        assert data["priority"] == "URGENT"

    def test_meeting_request_routed_medium(self):
        msg_id = self._insert_and_classify(
            "ceo@acme.com", "Let's schedule a call",
            "Would love to find 30 minutes to discuss next steps.")

        rc, out, _ = run_cli(ROUTE_SCRIPT, [
            "route", "--message-id", str(msg_id),
            "--route", "meeting", "--priority", "MEDIUM",
            "--actions", '["create_meeting_prep"]',
        ], self.env)
        data = parse_json_output(out)
        assert data["route"] == "meeting"

    def test_new_intro_creates_deal_and_routes(self):
        """New intro → auto-create deal → route as intro."""
        cursor = self.conn.execute(
            """INSERT INTO messages
               (source, source_id, type, sender, subject, body, timestamp,
                channel, attachments, project_tags)
               VALUES ('outlook', 'intro-001', 'email', 'vc@partner.com',
                       'Intro: Amazing Startup', 'Let me introduce you to the founder...',
                       ?, 'inbox', '[]', '[]')""",
            (datetime.now().isoformat(),),
        )
        self.conn.commit()
        msg_id = cursor.lastrowid

        # Auto-create
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "auto-create", "--type", "deal", "--name", "Amazing Startup",
            "--message-id", str(msg_id),
        ], self.env)
        assert parse_json_output(out)["status"] == "created"

        # Route
        rc, out, _ = run_cli(ROUTE_SCRIPT, [
            "route", "--message-id", str(msg_id),
            "--route", "intro", "--priority", "MEDIUM",
            "--actions", '["create_deal", "run_web_research"]',
        ], self.env)
        data = parse_json_output(out)
        assert data["route"] == "intro"

    def test_batch_mixed_messages(self):
        """10 mixed messages → correct route distribution."""
        msg_ids = []
        for i in range(10):
            mid = self._insert_and_classify(
                f"user{i}@acme.com", f"Message {i}", f"Body {i}")
            msg_ids.append(mid)

        decisions = [
            {"message_id": msg_ids[0], "route": "term_sheet", "priority": "URGENT", "actions": ["flag"]},
            {"message_id": msg_ids[1], "route": "dataroom", "priority": "HIGH", "actions": ["download"]},
            {"message_id": msg_ids[2], "route": "meeting", "priority": "MEDIUM", "actions": ["prep"]},
            {"message_id": msg_ids[3], "route": "intro", "priority": "MEDIUM", "actions": ["research"]},
            {"message_id": msg_ids[4], "route": "funding", "priority": "LOW", "actions": ["update"]},
            {"message_id": msg_ids[5], "route": "action_items", "priority": "LOW", "actions": ["extract"]},
            {"message_id": msg_ids[6], "route": "follow_up", "priority": "LOW", "actions": ["touch"]},
        ]
        # Mark rest as no-action
        run_cli(ROUTE_SCRIPT, [
            "mark-routed", "--message-ids", ",".join(str(m) for m in msg_ids[7:]),
        ], self.env)

        rc, out, _ = run_cli(ROUTE_SCRIPT, [
            "batch-route", "--decisions", json.dumps(decisions),
        ], self.env)
        data = parse_json_output(out)
        assert data["routed"] == 7

        # Verify all routed
        rc, out, _ = run_cli(ROUTE_SCRIPT, ["pending"], self.env)
        assert parse_json_output(out)["pending_count"] == 0

    def test_already_routed_excluded(self):
        """Already-routed messages don't appear in pending."""
        msg_id = self._insert_and_classify("a@acme.com", "Test", "Test body")

        run_cli(ROUTE_SCRIPT, [
            "route", "--message-id", str(msg_id),
            "--route", "follow_up", "--priority", "LOW",
            "--actions", '["update"]',
        ], self.env)

        rc, out, _ = run_cli(ROUTE_SCRIPT, ["pending"], self.env)
        data = parse_json_output(out)
        assert data["pending_count"] == 0
