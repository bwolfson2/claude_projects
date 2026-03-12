"""
System-level tests simulating the /monitor sweep.

Full end-to-end: messages → classify → route → action plan.
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


class TestMonitorSweep:

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
            {"slug": "midbound", "company_name": "Midbound", "status": "active",
             "domains": ["midbound.com"], "contact_emails": ["ceo@midbound.com"]},
            {"slug": "acme", "company_name": "Acme Corp", "status": "active",
             "domains": ["acme.com"], "contact_emails": ["jane@acme.com"]},
        ]))
        (tmp_path / "projects" / "projects.json").write_text(json.dumps([
            {"slug": "fund-ops", "project_name": "Fund Ops", "status": "active"},
        ]))
        self.env = {"VFT_REPO_ROOT": str(tmp_path)}

    def _insert_messages(self, messages):
        ids = []
        for m in messages:
            cursor = self.conn.execute(
                """INSERT INTO messages
                   (source, source_id, type, sender, subject, body, timestamp,
                    channel, attachments, project_tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '[]')""",
                (m["source"], m["source_id"], m.get("type", "email"),
                 m["sender"], m.get("subject", ""), m.get("body", ""),
                 m.get("timestamp", datetime.now().isoformat()),
                 m.get("channel", "inbox"), m.get("attachments", "[]")),
            )
            ids.append(cursor.lastrowid)
        self.conn.commit()
        return ids

    def test_full_sweep_20_messages(self):
        """Simulate full /monitor sweep with 20 messages across 4 sources."""
        messages = []
        for i in range(5):
            messages.append({"source": "outlook", "source_id": f"ol-{i}",
                            "sender": f"user{i}@midbound.com", "subject": f"Email {i}",
                            "body": f"Content {i}"})
        for i in range(5):
            messages.append({"source": "slack", "source_id": f"sl-{i}", "type": "message",
                            "sender": f"slack_user_{i}", "subject": f"Slack {i}",
                            "body": f"Slack content {i}", "channel": "#deals"})
        for i in range(5):
            messages.append({"source": "signal", "source_id": f"sig-{i}", "type": "message",
                            "sender": f"+1555000{i:04d}", "body": f"Signal msg {i}"})
        for i in range(5):
            messages.append({"source": "granola", "source_id": f"gr-{i}", "type": "transcript",
                            "sender": "Granola", "subject": f"Meeting {i}",
                            "body": f"Transcript {i}"})

        ids = self._insert_messages(messages)

        # Phase 1: Verify all pending
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        assert parse_json_output(out)["pending_count"] == 20

        # Phase 2: Classify all to midbound
        decisions = [
            {"message_id": mid, "slug": "midbound", "match_type": "deal", "confidence": 0.9}
            for mid in ids
        ]
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "batch-classify", "--decisions", json.dumps(decisions),
        ], self.env)
        assert parse_json_output(out)["classified"] == 20

        # Phase 3: Route all
        route_decisions = [
            {"message_id": mid, "route": "follow_up", "priority": "LOW",
             "actions": ["update_last_touch"]}
            for mid in ids
        ]
        rc, out, _ = run_cli(ROUTE_SCRIPT, [
            "batch-route", "--decisions", json.dumps(route_decisions),
        ], self.env)
        assert parse_json_output(out)["routed"] == 20

        # Phase 4: Nothing pending
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        assert parse_json_output(out)["pending_count"] == 0
        rc, out, _ = run_cli(ROUTE_SCRIPT, ["pending"], self.env)
        assert parse_json_output(out)["pending_count"] == 0

    def test_sweep_with_urgent_and_routine(self):
        """1 urgent term sheet + 3 routine → urgent flagged."""
        msgs = [
            {"source": "outlook", "source_id": "ts-1", "sender": "legal@acme.com",
             "subject": "Term Sheet - Acme", "body": "Please review the term sheet"},
            {"source": "outlook", "source_id": "rt-1", "sender": "info@midbound.com",
             "subject": "Update", "body": "Monthly update"},
            {"source": "outlook", "source_id": "rt-2", "sender": "info@midbound.com",
             "subject": "Newsletter", "body": "Our newsletter"},
            {"source": "slack", "source_id": "rt-3", "type": "message",
             "sender": "bot", "subject": "Reminder", "body": "Don't forget"},
        ]
        ids = self._insert_messages(msgs)

        # Classify
        decisions = [
            {"message_id": ids[0], "slug": "acme", "match_type": "deal", "confidence": 0.95},
            {"message_id": ids[1], "slug": "midbound", "match_type": "deal", "confidence": 0.8},
            {"message_id": ids[2], "slug": "midbound", "match_type": "deal", "confidence": 0.7},
            {"message_id": ids[3], "slug": "fund-ops", "match_type": "project", "confidence": 0.6},
        ]
        run_cli(CLASSIFY_SCRIPT, ["batch-classify", "--decisions", json.dumps(decisions)], self.env)

        # Route with urgent
        route_decisions = [
            {"message_id": ids[0], "route": "term_sheet", "priority": "URGENT",
             "actions": ["flag_urgent", "save_to_diligence"]},
            {"message_id": ids[1], "route": "follow_up", "priority": "LOW",
             "actions": ["update_last_touch"]},
            {"message_id": ids[2], "route": "follow_up", "priority": "LOW",
             "actions": ["update_last_touch"]},
            {"message_id": ids[3], "route": "action_items", "priority": "LOW",
             "actions": ["extract_action_items"]},
        ]
        rc, out, _ = run_cli(ROUTE_SCRIPT, [
            "batch-route", "--decisions", json.dumps(route_decisions),
        ], self.env)
        data = parse_json_output(out)
        urgent = [a for a in data["action_plan"] if a["priority"] == "URGENT"]
        assert len(urgent) == 1
        assert urgent[0]["route"] == "term_sheet"

    def test_sweep_empty_system(self):
        """Sweep on empty system → all zeros."""
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        assert parse_json_output(out)["pending_count"] == 0

    def test_sweep_after_previous_sweep(self):
        """Second sweep finds nothing new."""
        msgs = [{"source": "outlook", "source_id": "s1", "sender": "a@b.com",
                 "subject": "Test", "body": "Body"}]
        ids = self._insert_messages(msgs)

        # First sweep
        run_cli(CLASSIFY_SCRIPT, [
            "classify", "--message-id", str(ids[0]),
            "--slug", "midbound", "--match-type", "deal",
        ], self.env)
        run_cli(ROUTE_SCRIPT, [
            "route", "--message-id", str(ids[0]),
            "--route", "follow_up", "--priority", "LOW",
            "--actions", '["update"]',
        ], self.env)

        # Second sweep: nothing pending
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        assert parse_json_output(out)["pending_count"] == 0
        rc, out, _ = run_cli(ROUTE_SCRIPT, ["pending"], self.env)
        assert parse_json_output(out)["pending_count"] == 0

    def test_sweep_new_company_auto_create(self):
        """New company messages → auto-create deals."""
        msgs = [
            {"source": "outlook", "source_id": "new-1", "sender": "ceo@brandnew.io",
             "subject": "Intro: BrandNew", "body": "Would love to pitch our startup"},
        ]
        ids = self._insert_messages(msgs)

        # Auto-create
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "auto-create", "--type", "deal", "--name", "BrandNew",
            "--message-id", str(ids[0]),
        ], self.env)
        data = parse_json_output(out)
        assert data["status"] == "created"
        assert data["slug"] == "brandnew"

        # Route
        rc, out, _ = run_cli(ROUTE_SCRIPT, [
            "route", "--message-id", str(ids[0]),
            "--route", "intro", "--priority", "MEDIUM",
            "--actions", '["create_deal", "run_web_research"]',
        ], self.env)
        assert rc == 0
