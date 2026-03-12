"""
Tests for sheet-sync scripts (sync_to_sheets.py and update_detail_tabs.py).

Verifies:
- Correct file paths (fund/crm/deals.json, projects/projects.json)
- Both dict-wrapper and flat-array JSON formats
- DD_STATUS_MAP mappings
- Truncation behaviour
- Deal/project filtering (skip passed/archived)
- Graceful handling of missing JSON files
"""

import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# Mock gspread before importing the sheet-sync scripts
mock_gspread = ModuleType("gspread")
mock_gspread.Client = MagicMock
mock_gspread.Spreadsheet = MagicMock
mock_gspread.Worksheet = MagicMock
mock_gspread.WorksheetNotFound = type("WorksheetNotFound", (Exception,), {})
mock_gspread.service_account = MagicMock()
sys.modules["gspread"] = mock_gspread

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "skills" / "sheet-sync" / "scripts"))


# ── Path Tests ────────────────────────────────────────────────────────────


class TestPaths:
    """Verify the JSON paths resolve correctly."""

    def test_deals_json_path(self):
        from sync_to_sheets import DEALS_JSON
        assert DEALS_JSON.parts[-3:] == ("fund", "crm", "deals.json")

    def test_projects_json_path(self):
        from sync_to_sheets import PROJECTS_JSON
        assert PROJECTS_JSON.parts[-2:] == ("projects", "projects.json")

    def test_contacts_json_path(self):
        from sync_to_sheets import CONTACTS_JSON
        assert CONTACTS_JSON.parts[-3:] == ("fund", "crm", "contacts.json")

    def test_detail_tabs_deals_json_path(self):
        from update_detail_tabs import DEALS_JSON
        assert DEALS_JSON.parts[-3:] == ("fund", "crm", "deals.json")

    def test_detail_tabs_projects_json_path(self):
        from update_detail_tabs import PROJECTS_JSON
        assert PROJECTS_JSON.parts[-2:] == ("projects", "projects.json")


# ── Format Handling Tests ────────────────────────────────────────────────


class TestFormatHandling:
    """Verify both dict-wrapper and flat-array formats work."""

    def _mock_spreadsheet(self):
        sh = MagicMock()
        ws = MagicMock()
        sh.worksheet.return_value = ws
        ws.update = MagicMock()
        ws.batch_clear = MagicMock()
        return sh, ws

    def test_sync_deals_dict_wrapper(self, tmp_path):
        """{"companies": [...]} format should iterate over the array."""
        from sync_to_sheets import sync_deals, DEALS_JSON

        deals_data = {"companies": [
            {"company_name": "TestCo", "stage": "sourcing", "status": "active"},
        ]}
        deals_file = tmp_path / "deals.json"
        deals_file.write_text(json.dumps(deals_data))

        sh, ws = self._mock_spreadsheet()

        with patch("sync_to_sheets.DEALS_JSON", deals_file):
            count = sync_deals(sh)

        assert count == 1
        ws.update.assert_called_once()
        rows = ws.update.call_args[0][0]
        assert rows[0][0] == "TestCo"

    def test_sync_deals_flat_array(self, tmp_path):
        """Flat array [...] format should also work (backward compat)."""
        from sync_to_sheets import sync_deals

        deals_data = [
            {"company_name": "FlatCo", "stage": "ic", "status": "active"},
        ]
        deals_file = tmp_path / "deals.json"
        deals_file.write_text(json.dumps(deals_data))

        sh, ws = self._mock_spreadsheet()

        with patch("sync_to_sheets.DEALS_JSON", deals_file):
            count = sync_deals(sh)

        assert count == 1
        rows = ws.update.call_args[0][0]
        assert rows[0][0] == "FlatCo"

    def test_sync_projects_dict_wrapper(self, tmp_path):
        """{"projects": [...]} format should iterate over the array."""
        from sync_to_sheets import sync_projects

        projects_data = {"projects": [
            {"project_name": "TestProj", "project_type": "hiring", "status": "active"},
        ]}
        projects_file = tmp_path / "projects.json"
        projects_file.write_text(json.dumps(projects_data))

        sh, ws = self._mock_spreadsheet()

        with patch("sync_to_sheets.PROJECTS_JSON", projects_file):
            count = sync_projects(sh)

        assert count == 1
        rows = ws.update.call_args[0][0]
        assert rows[0][0] == "TestProj"

    def test_sync_projects_flat_array(self, tmp_path):
        """Flat array [...] format should also work."""
        from sync_to_sheets import sync_projects

        projects_data = [
            {"project_name": "FlatProj", "project_type": "ops", "status": "active"},
        ]
        projects_file = tmp_path / "projects.json"
        projects_file.write_text(json.dumps(projects_data))

        sh, ws = self._mock_spreadsheet()

        with patch("sync_to_sheets.PROJECTS_JSON", projects_file):
            count = sync_projects(sh)

        assert count == 1
        rows = ws.update.call_args[0][0]
        assert rows[0][0] == "FlatProj"

    def test_update_deal_tabs_dict_wrapper(self, tmp_path):
        """update_detail_tabs should handle {"companies": [...]} format."""
        from update_detail_tabs import update_deal_tabs

        deals_data = {"companies": [
            {"company_name": "DetailCo", "slug": "detailco", "status": "active"},
        ]}
        deals_file = tmp_path / "deals.json"
        deals_file.write_text(json.dumps(deals_data))

        sh = MagicMock()
        ws = MagicMock()
        sh.worksheet.side_effect = mock_gspread.WorksheetNotFound("not found")
        sh.add_worksheet.return_value = ws

        with patch("update_detail_tabs.DEALS_JSON", deals_file), \
             patch("update_detail_tabs.DB_PATH", tmp_path / "nonexistent.db"):
            count = update_deal_tabs(sh)

        assert count == 1

    def test_update_project_tabs_dict_wrapper(self, tmp_path):
        """update_detail_tabs should handle {"projects": [...]} format."""
        from update_detail_tabs import update_project_tabs

        projects_data = {"projects": [
            {"project_name": "DetailProj", "slug": "detailproj", "status": "active"},
        ]}
        projects_file = tmp_path / "projects.json"
        projects_file.write_text(json.dumps(projects_data))

        sh = MagicMock()
        ws = MagicMock()
        sh.worksheet.side_effect = mock_gspread.WorksheetNotFound("not found")
        sh.add_worksheet.return_value = ws

        with patch("update_detail_tabs.PROJECTS_JSON", projects_file), \
             patch("update_detail_tabs.DB_PATH", tmp_path / "nonexistent.db"):
            count = update_project_tabs(sh)

        assert count == 1


# ── Missing File Tests ───────────────────────────────────────────────────


class TestMissingFiles:
    """Verify graceful skip when JSON files don't exist."""

    def test_sync_deals_missing_file(self, tmp_path):
        sh = MagicMock()
        with patch("sync_to_sheets.DEALS_JSON", tmp_path / "nonexistent.json"):
            from sync_to_sheets import sync_deals
            count = sync_deals(sh)
        assert count == 0

    def test_sync_projects_missing_file(self, tmp_path):
        sh = MagicMock()
        with patch("sync_to_sheets.PROJECTS_JSON", tmp_path / "nonexistent.json"):
            from sync_to_sheets import sync_projects
            count = sync_projects(sh)
        assert count == 0

    def test_update_deal_tabs_missing_file(self, tmp_path):
        sh = MagicMock()
        with patch("update_detail_tabs.DEALS_JSON", tmp_path / "nonexistent.json"):
            from update_detail_tabs import update_deal_tabs
            count = update_deal_tabs(sh)
        assert count == 0

    def test_update_project_tabs_missing_file(self, tmp_path):
        sh = MagicMock()
        with patch("update_detail_tabs.PROJECTS_JSON", tmp_path / "nonexistent.json"):
            from update_detail_tabs import update_project_tabs
            count = update_project_tabs(sh)
        assert count == 0


# ── Filtering Tests ──────────────────────────────────────────────────────


class TestFiltering:
    """Verify deal/project status filtering."""

    def test_skip_passed_deals(self, tmp_path):
        """Passed deals should be skipped in detail tabs."""
        from update_detail_tabs import update_deal_tabs

        deals_data = {"companies": [
            {"company_name": "Active", "slug": "active", "status": "active"},
            {"company_name": "Passed", "slug": "passed", "status": "passed"},
        ]}
        deals_file = tmp_path / "deals.json"
        deals_file.write_text(json.dumps(deals_data))

        sh = MagicMock()
        ws = MagicMock()
        sh.worksheet.side_effect = mock_gspread.WorksheetNotFound("not found")
        sh.add_worksheet.return_value = ws

        with patch("update_detail_tabs.DEALS_JSON", deals_file), \
             patch("update_detail_tabs.DB_PATH", tmp_path / "nonexistent.db"):
            count = update_deal_tabs(sh)

        assert count == 1  # Only the active deal

    def test_skip_archived_projects(self, tmp_path):
        """Archived and cancelled projects should be skipped."""
        from update_detail_tabs import update_project_tabs

        projects_data = {"projects": [
            {"project_name": "Active", "slug": "active", "status": "active"},
            {"project_name": "Archived", "slug": "archived", "status": "archived"},
            {"project_name": "Cancelled", "slug": "cancelled", "status": "cancelled"},
        ]}
        projects_file = tmp_path / "projects.json"
        projects_file.write_text(json.dumps(projects_data))

        sh = MagicMock()
        ws = MagicMock()
        sh.worksheet.side_effect = mock_gspread.WorksheetNotFound("not found")
        sh.add_worksheet.return_value = ws

        with patch("update_detail_tabs.PROJECTS_JSON", projects_file), \
             patch("update_detail_tabs.DB_PATH", tmp_path / "nonexistent.db"):
            count = update_project_tabs(sh)

        assert count == 1  # Only the active project


# ── DD_STATUS_MAP Tests ──────────────────────────────────────────────────


class TestDDStatusMap:
    """Verify diligence status display mapping."""

    def test_status_map_keys(self):
        from sync_to_sheets import DD_STATUS_MAP
        assert DD_STATUS_MAP["complete"] == "Done"
        assert DD_STATUS_MAP["in_progress"] == "In Progress"
        assert DD_STATUS_MAP["pending"] == "Pending"
        assert DD_STATUS_MAP["not_started"] == "Not Started"
        assert DD_STATUS_MAP["blocked"] == "Blocked"

    def test_empty_maps_to_dash(self):
        from sync_to_sheets import DD_STATUS_MAP
        assert DD_STATUS_MAP[""] == "—"
        assert DD_STATUS_MAP[None] == "—"


# ── Truncation Tests ─────────────────────────────────────────────────────


class TestTruncation:
    """Verify text truncation utility."""

    def test_truncate_long_text(self):
        from sync_to_sheets import truncate
        result = truncate("A" * 300, 200)
        assert len(result) == 203  # 200 + "..."
        assert result.endswith("...")

    def test_truncate_short_text(self):
        from sync_to_sheets import truncate
        result = truncate("short", 200)
        assert result == "short"

    def test_truncate_empty(self):
        from sync_to_sheets import truncate
        assert truncate("") == ""
        assert truncate(None) == ""
