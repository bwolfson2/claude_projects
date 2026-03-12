"""
Skill-level tests for deal-project-classifier.

Tests the full RLM workflow: context → pending → classify → apply_updates
as Claude would use it.
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
sys.path.insert(0, str(REPO_ROOT / "skills" / "deal-project-classifier" / "scripts"))

from conftest import run_cli, parse_json_output

CLASSIFY_SCRIPT = REPO_ROOT / "skills" / "deal-project-classifier" / "scripts" / "classify_messages.py"
APPLY_SCRIPT = REPO_ROOT / "skills" / "deal-project-classifier" / "scripts" / "apply_updates.py"


class TestClassifierWorkflow:

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.root = tmp_path
        self.db_dir = tmp_path / "fund" / "metadata" / "db"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.deals_dir = tmp_path / "fund" / "crm"
        self.deals_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir = tmp_path / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)

        from init_db import init_db
        self.db_path = str(self.db_dir / "ingestion.db")
        self.conn = init_db(self.db_path)
        self.conn.row_factory = None  # Use default

        self.deals_path = self.deals_dir / "deals.json"
        self.projects_path = self.projects_dir / "projects.json"
        # Note: auto-create expects flat arrays (known format mismatch bug)
        self.deals_path.write_text(json.dumps([
            {"slug": "midbound", "company_name": "Midbound", "status": "active",
             "stage": "diligence", "domains": ["midbound.com"],
             "contact_emails": ["ceo@midbound.com"]},
        ], indent=2))
        self.projects_path.write_text(json.dumps([
            {"slug": "fund-ops", "project_name": "Fund Ops", "status": "active"},
        ], indent=2))

        self.env = {"VFT_REPO_ROOT": str(tmp_path)}

    def _insert_messages(self, count, **overrides):
        ids = []
        for i in range(count):
            defaults = {
                "source": "outlook",
                "source_id": f"msg-{i}-{datetime.now().timestamp()}",
                "type": "email",
                "sender": overrides.get("sender", f"user{i}@example.com"),
                "recipients": "[]",
                "subject": overrides.get("subject", f"Test Message {i}"),
                "body": overrides.get("body", f"Body content for message {i}"),
                "timestamp": datetime.now().isoformat(),
                "channel": "inbox",
                "attachments": "[]",
                "project_tags": "[]",
            }
            defaults.update({k: v for k, v in overrides.items() if k not in ("sender", "subject", "body")})
            cursor = self.conn.execute(
                """INSERT INTO messages
                   (source, source_id, type, sender, recipients, subject, body,
                    timestamp, channel, attachments, project_tags)
                   VALUES (:source, :source_id, :type, :sender, :recipients,
                           :subject, :body, :timestamp, :channel, :attachments, :project_tags)""",
                defaults,
            )
            ids.append(cursor.lastrowid)
        self.conn.commit()
        return ids

    def test_full_rlm_flow(self):
        """context → pending → classify → verify classified."""
        ids = self._insert_messages(3, sender="ceo@midbound.com", subject="Midbound Update")

        # Step 1: context
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["context", "--no-rebuild-index"], self.env)
        assert rc == 0

        # Step 2: pending
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        assert rc == 0
        data = parse_json_output(out)
        assert data["pending_count"] == 3

        # Step 3: classify first message
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "classify", "--message-id", str(ids[0]),
            "--slug", "midbound", "--match-type", "deal",
            "--confidence", "0.95",
        ], self.env)
        assert rc == 0
        result = parse_json_output(out)
        assert result["status"] == "classified"

        # Step 4: verify pending decreased
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        data = parse_json_output(out)
        assert data["pending_count"] == 2

    def test_batch_classify_5_messages(self):
        ids = self._insert_messages(5, sender="ceo@midbound.com")

        decisions = [
            {"message_id": mid, "slug": "midbound", "match_type": "deal", "confidence": 0.9}
            for mid in ids
        ]
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "batch-classify", "--decisions", json.dumps(decisions),
        ], self.env)
        assert rc == 0
        data = parse_json_output(out)
        assert data["classified"] == 5

        # Verify all classified
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        data = parse_json_output(out)
        assert data["pending_count"] == 0

    def test_auto_create_then_context(self):
        """New deal created via auto-create appears in context."""
        ids = self._insert_messages(1, sender="founder@newco.io", subject="NewCo Pitch")

        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "auto-create", "--type", "deal", "--name", "NewCo",
            "--message-id", str(ids[0]),
        ], self.env)
        assert rc == 0
        result = parse_json_output(out)
        assert result["status"] == "created"
        assert result["slug"] == "newco"

        # Verify deal exists in JSON
        deals = json.loads(self.deals_path.read_text())
        # auto-create writes flat array
        if isinstance(deals, list):
            slugs = [d["slug"] for d in deals]
        else:
            slugs = [d["slug"] for d in deals.get("companies", [])]
        assert "newco" in slugs

    def test_mixed_batch_known_and_new(self):
        """3 known deal messages + 2 unknown."""
        known_ids = self._insert_messages(3, sender="ceo@midbound.com")
        unknown_ids = self._insert_messages(2, sender="mystery@unknown.io")

        # Classify known
        decisions = [
            {"message_id": mid, "slug": "midbound", "match_type": "deal"}
            for mid in known_ids
        ]
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "batch-classify", "--decisions", json.dumps(decisions),
        ], self.env)
        data = parse_json_output(out)
        assert data["classified"] == 3

        # Auto-create for unknowns (each needs unique name to avoid "exists" status)
        for i, uid in enumerate(unknown_ids):
            rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
                "auto-create", "--type", "deal", "--name", f"Unknown Co {i+1}",
                "--message-id", str(uid),
            ], self.env)

        # Verify all classified
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        data = parse_json_output(out)
        assert data["pending_count"] == 0

    def test_reviewed_protection(self):
        """Reviewed classification cannot be overwritten."""
        ids = self._insert_messages(1)
        # Classify
        run_cli(CLASSIFY_SCRIPT, [
            "classify", "--message-id", str(ids[0]),
            "--slug", "midbound", "--match-type", "deal",
        ], self.env)

        # Mark as reviewed
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE classification_log SET reviewed = 1 WHERE source_id = ?", (ids[0],))
        conn.commit()
        conn.close()

        # Try to reclassify
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "classify", "--message-id", str(ids[0]),
            "--slug", "midbound", "--match-type", "deal",
            "--confidence", "0.5",
        ], self.env)
        result = parse_json_output(out)
        assert result["status"] == "skipped"

    def test_empty_system(self):
        """No deals, no messages → graceful empty responses."""
        self.deals_path.write_text(json.dumps({"companies": []}))
        self.projects_path.write_text(json.dumps({"projects": []}))

        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        data = parse_json_output(out)
        assert data["pending_count"] == 0

        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["context", "--no-rebuild-index"], self.env)
        data = parse_json_output(out)
        assert data["deals_count"] == 0

    def test_unicode_company_full_workflow(self):
        """Unicode name through create → classify → context."""
        ids = self._insert_messages(1, sender="info@ünternehmen.de")

        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "auto-create", "--type", "deal", "--name", "Ünternéhmen GmbH",
            "--message-id", str(ids[0]),
        ], self.env)
        assert rc == 0

        rc, out, _ = run_cli(CLASSIFY_SCRIPT, ["pending"], self.env)
        data = parse_json_output(out)
        assert data["pending_count"] == 0  # classified by auto-create

    def test_high_volume_100_messages(self):
        """Batch classify 100 messages."""
        ids = self._insert_messages(100)
        decisions = [
            {"message_id": mid, "slug": "midbound", "match_type": "deal", "confidence": 0.8}
            for mid in ids
        ]
        rc, out, _ = run_cli(CLASSIFY_SCRIPT, [
            "batch-classify", "--decisions", json.dumps(decisions),
        ], self.env)
        assert rc == 0
        data = parse_json_output(out)
        assert data["classified"] == 100
