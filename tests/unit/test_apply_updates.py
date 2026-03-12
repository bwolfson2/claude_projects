"""
Tests for apply_updates.py — Pipeline Updater

Tests the application of classification results to deals.json and projects.json.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "fund" / "metadata"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "deal-project-classifier" / "scripts"))


class TestApplyUpdates:
    """Test apply_updates.apply_all_updates function."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up isolated environment for each test."""
        self.tmp = tmp_path
        self.db_path = tmp_path / "fund" / "metadata" / "db" / "ingestion.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.deals_path = tmp_path / "fund" / "crm" / "deals.json"
        self.deals_path.parent.mkdir(parents=True, exist_ok=True)
        self.projects_path = tmp_path / "projects" / "projects.json"
        self.projects_path.parent.mkdir(parents=True, exist_ok=True)

        # Init DB
        from init_db import init_db
        self.conn = init_db(str(self.db_path))

        # Default deals/projects JSON
        self.deals_data = {
            "companies": [
                {"slug": "midbound", "company_name": "Midbound", "status": "active",
                 "stage": "diligence", "last_touch": "2026-03-01"},
                {"slug": "acme-corp", "company_name": "Acme Corp", "status": "active",
                 "stage": "sourced", "last_touch": "2026-02-15"},
            ],
            "last_updated": "2026-03-01",
        }
        self.projects_data = {
            "projects": [
                {"slug": "fund-ops", "project_name": "Fund Ops", "status": "active",
                 "last_updated": "2026-03-01"},
            ],
            "last_updated": "2026-03-01",
        }
        self._write_json()

    def _write_json(self):
        self.deals_path.write_text(json.dumps(self.deals_data, indent=2))
        self.projects_path.write_text(json.dumps(self.projects_data, indent=2))

    def _insert_email(self, id_val, sender="test@test.com", subject="Test"):
        self.conn.execute(
            "INSERT INTO emails (id, outlook_id, subject, sender, date) VALUES (?, ?, ?, ?, ?)",
            (id_val, f"out-{id_val}", subject, sender, "2026-03-10"),
        )
        self.conn.commit()

    def _insert_classification(self, source_id, slug, match_type, source_type="email"):
        self.conn.execute(
            """INSERT INTO classification_log
               (source_type, source_id, matched_slug, match_type, confidence, rule_hits)
               VALUES (?, ?, ?, ?, 0.9, '{}')""",
            (source_type, source_id, slug, match_type),
        )
        self.conn.commit()

    def _run_apply(self, dry_run=False):
        import apply_updates as au
        # Monkeypatch paths
        au.REPO_ROOT = self.tmp
        au.DB_PATH = self.db_path
        au.DEALS_PATH = self.deals_path
        au.PROJECTS_PATH = self.projects_path
        au.TRACKER_SYNC = self.tmp / "nonexistent_sync.py"  # no tracker
        return au.apply_all_updates(dry_run=dry_run)

    def test_no_pending_classifications(self):
        stats = self._run_apply()
        assert stats["applied"] == 0

    def test_deal_update_last_touch(self):
        self._insert_email(1, sender="ceo@midbound.com")
        self._insert_classification(1, "midbound", "deal")
        stats = self._run_apply()
        assert stats["deal_updates"] == 1
        deals = json.loads(self.deals_path.read_text())
        midbound = next(c for c in deals["companies"] if c["slug"] == "midbound")
        assert midbound["last_touch"] == datetime.now().strftime("%Y-%m-%d")

    def test_deal_slug_not_found_skipped(self):
        self._insert_email(1)
        self._insert_classification(1, "nonexistent-deal", "deal")
        stats = self._run_apply()
        assert stats["skipped"] == 1

    def test_project_update_last_updated(self):
        self._insert_email(1)
        self._insert_classification(1, "fund-ops", "project")
        stats = self._run_apply()
        assert stats["project_updates"] == 1

    def test_new_deal_created(self):
        self._insert_email(1, sender="founder@newco.com", subject="NewCo Pitch")
        self._insert_classification(1, None, "new_deal")
        stats = self._run_apply()
        assert len(stats["new_deals"]) == 1
        deals = json.loads(self.deals_path.read_text())
        slugs = [c["slug"] for c in deals["companies"]]
        assert stats["new_deals"][0] in slugs

    def test_new_deal_slug_dedup(self):
        """Second deal with same name gets -2 suffix."""
        self._insert_email(1, sender="a@midbound.com", subject="Midbound")
        self._insert_classification(1, None, "new_deal")
        stats = self._run_apply()
        # "midbound" already exists, so slug should be "midbound-2"
        assert "midbound-2" in stats["new_deals"]

    def test_new_project_created(self):
        self._insert_email(1, subject="New Research Topic")
        self._insert_classification(1, None, "new_project")
        stats = self._run_apply()
        assert len(stats["new_projects"]) == 1

    def test_vft_no_auto_create_env(self):
        self._insert_email(1)
        self._insert_classification(1, None, "new_deal")
        with patch.dict(os.environ, {"VFT_NO_AUTO_CREATE": "1"}):
            stats = self._run_apply()
        assert stats["skipped"] == 1
        assert len(stats["new_deals"]) == 0

    def test_dry_run_no_writes(self):
        original_deals = self.deals_path.read_text()
        self._insert_email(1, sender="ceo@midbound.com")
        self._insert_classification(1, "midbound", "deal")
        stats = self._run_apply(dry_run=True)
        # File should be unchanged
        assert self.deals_path.read_text() == original_deals

    def test_processed_dedup_second_run(self):
        """Second run finds nothing to process."""
        self._insert_email(1, sender="ceo@midbound.com")
        self._insert_classification(1, "midbound", "deal")
        self._run_apply()
        stats2 = self._run_apply()
        assert stats2["applied"] == 0

    def test_infer_company_from_corporate_domain(self):
        import apply_updates as au
        name = au.infer_company_name(
            {"sender": "ceo@widgetco.com", "sender_domain": "widgetco.com"},
            "email"
        )
        assert name == "Widgetco"

    def test_infer_company_from_generic_domain(self):
        import apply_updates as au
        name = au.infer_company_name(
            {"sender": "user@gmail.com", "sender_domain": "gmail.com",
             "subject": "Interesting Startup Pitch"},
            "email"
        )
        assert name == "Interesting Startup Pitch"

    def test_missing_source_item_skipped(self):
        """Classification references nonexistent email."""
        self._insert_classification(999, "midbound", "deal")
        stats = self._run_apply()
        assert stats["skipped"] == 1

    def test_slugify_truncation(self):
        import apply_updates as au
        slug = au.slugify("A" * 100)
        assert len(slug) <= 40

    def test_slugify_special_chars(self):
        import apply_updates as au
        slug = au.slugify("Hello!@#$%^&*()World")
        assert slug == "hello-world"

    def test_tracker_sync_missing_no_crash(self):
        """Missing tracker sync script doesn't crash."""
        self._insert_email(1, sender="ceo@midbound.com")
        self._insert_classification(1, "midbound", "deal")
        stats = self._run_apply()
        assert stats["deal_updates"] == 1  # completed without crash

    def test_multi_match_same_message(self):
        """One message classified to 2 different slugs."""
        self._insert_email(1, sender="shared@test.com")
        self._insert_classification(1, "midbound", "deal")
        # Second classification for same source_id but different slug
        self.conn.execute(
            """INSERT INTO classification_log
               (source_type, source_id, matched_slug, match_type, confidence, rule_hits)
               VALUES ('email', 1, 'acme-corp', 'deal', 0.8, '{}')""")
        self.conn.commit()
        stats = self._run_apply()
        assert stats["deal_updates"] == 2

    def test_json_last_updated_set(self):
        self._insert_email(1, sender="ceo@midbound.com")
        self._insert_classification(1, "midbound", "deal")
        self._run_apply()
        deals = json.loads(self.deals_path.read_text())
        assert deals["last_updated"] == datetime.now().strftime("%Y-%m-%d")
