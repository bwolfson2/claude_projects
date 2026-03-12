"""
Skill-level tests for reactive-router.

Tests the full routing workflow: pending → route → verify.
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

ROUTE_SCRIPT = REPO_ROOT / "skills" / "reactive-router" / "scripts" / "route_messages.py"
CLASSIFY_SCRIPT = REPO_ROOT / "skills" / "deal-project-classifier" / "scripts" / "classify_messages.py"


class TestRouterWorkflow:

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

        # Write minimal JSON files
        (tmp_path / "fund" / "crm" / "deals.json").write_text('[]')
        (tmp_path / "projects" / "projects.json").write_text('[]')

        self.env = {"VFT_REPO_ROOT": str(tmp_path)}

    def _insert_classified_messages(self, count):
        """Insert messages that are classified but not routed."""
        ids = []
        for i in range(count):
            cursor = self.conn.execute(
                """INSERT INTO messages
                   (source, source_id, type, sender, subject, body, timestamp,
                    channel, attachments, project_tags, classified)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                ("outlook", f"msg-{i}-{datetime.now().timestamp()}", "email",
                 f"user{i}@test.com", f"Subject {i}", f"Body {i}",
                 datetime.now().isoformat(), "inbox", "[]", "[]"),
            )
            ids.append(cursor.lastrowid)
        self.conn.commit()
        return ids

    def test_full_route_flow(self):
        """pending → route → verify routed_at set."""
        ids = self._insert_classified_messages(1)

        rc, out, _ = run_cli(ROUTE_SCRIPT, ["pending"], self.env)
        assert rc == 0
        data = parse_json_output(out)
        assert data["pending_count"] == 1

        rc, out, _ = run_cli(ROUTE_SCRIPT, [
            "route", "--message-id", str(ids[0]),
            "--route", "meeting", "--priority", "MEDIUM",
            "--actions", '["create_meeting_prep"]',
        ], self.env)
        assert rc == 0

        # Verify routed
        rc, out, _ = run_cli(ROUTE_SCRIPT, ["pending"], self.env)
        data = parse_json_output(out)
        assert data["pending_count"] == 0

    def test_batch_route_mixed_priorities(self):
        ids = self._insert_classified_messages(3)

        decisions = [
            {"message_id": ids[0], "route": "term_sheet", "priority": "URGENT",
             "actions": ["flag_urgent"]},
            {"message_id": ids[1], "route": "meeting", "priority": "MEDIUM",
             "actions": ["create_meeting_prep"]},
            {"message_id": ids[2], "route": "follow_up", "priority": "LOW",
             "actions": ["update_last_touch"]},
        ]
        rc, out, _ = run_cli(ROUTE_SCRIPT, [
            "batch-route", "--decisions", json.dumps(decisions),
        ], self.env)
        assert rc == 0
        data = parse_json_output(out)
        assert data["routed"] == 3
        assert len(data["action_plan"]) == 3

    def test_mark_routed_excluded_from_pending(self):
        ids = self._insert_classified_messages(3)

        # Mark first two as no-action
        rc, _, _ = run_cli(ROUTE_SCRIPT, [
            "mark-routed", "--message-ids", f"{ids[0]},{ids[1]}",
        ], self.env)
        assert rc == 0

        # Only 1 should remain
        rc, out, _ = run_cli(ROUTE_SCRIPT, ["pending"], self.env)
        data = parse_json_output(out)
        assert data["pending_count"] == 1

    def test_all_7_route_types(self):
        ids = self._insert_classified_messages(7)
        routes = ["term_sheet", "dataroom", "meeting", "intro",
                  "funding", "action_items", "follow_up"]
        priorities = ["URGENT", "HIGH", "MEDIUM", "MEDIUM", "LOW", "LOW", "LOW"]

        decisions = [
            {"message_id": ids[i], "route": routes[i], "priority": priorities[i],
             "actions": [f"action_{routes[i]}"]}
            for i in range(7)
        ]
        rc, out, _ = run_cli(ROUTE_SCRIPT, [
            "batch-route", "--decisions", json.dumps(decisions),
        ], self.env)
        assert rc == 0
        data = parse_json_output(out)
        assert data["routed"] == 7

    def test_no_pending_messages(self):
        rc, out, _ = run_cli(ROUTE_SCRIPT, ["pending"], self.env)
        assert rc == 0
        data = parse_json_output(out)
        assert data["pending_count"] == 0
        assert data["messages"] == []

    def test_routes_reference(self):
        rc, out, _ = run_cli(ROUTE_SCRIPT, ["routes"], self.env)
        assert rc == 0
        data = parse_json_output(out)
        assert len(data["routes"]) == 7
        route_names = [r["route"] for r in data["routes"]]
        assert "term_sheet" in route_names
        assert "dataroom" in route_names
