"""
Tests for project-management scripts:
  - upsert_project.py (parse_value, set_path, append_path, CLI)
  - render_project_dashboard.py (build_dashboard, project_row)
"""

import json
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT, run_cli

# ── Direct imports for unit-level tests ──────────────────────────────────

sys.path.insert(0, str(REPO_ROOT / "skills" / "project-management" / "scripts"))
from upsert_project import parse_value as pm_parse_value
from upsert_project import set_path as pm_set_path
from render_project_dashboard import build_dashboard as pm_build_dashboard
from render_project_dashboard import project_row

# ── Script paths ─────────────────────────────────────────────────────────

UPSERT_PROJECT_SCRIPT = REPO_ROOT / "skills" / "project-management" / "scripts" / "upsert_project.py"
RENDER_PROJECT_DASHBOARD_SCRIPT = REPO_ROOT / "skills" / "project-management" / "scripts" / "render_project_dashboard.py"


# ── upsert_project: parse_value / set_path ───────────────────────────────

class TestUpsertProjectHelpers:
    def test_parse_value_json(self):
        """JSON string is deserialized to Python object."""
        assert pm_parse_value('{"key": "val"}') == {"key": "val"}

    def test_parse_value_plain(self):
        """Non-JSON string returned as-is."""
        assert pm_parse_value("some text") == "some text"

    def test_set_path_dotted_key(self):
        """Dotted key sets a nested value."""
        obj = {"meta": {"status": "old"}}
        pm_set_path(obj, "meta.status", "new")
        assert obj["meta"]["status"] == "new"

    def test_set_path_creates_intermediates(self):
        obj = {}
        pm_set_path(obj, "a.b.c", True)
        assert obj == {"a": {"b": {"c": True}}}


# ── upsert_project: CLI ─────────────────────────────────────────────────

class TestUpsertProjectCLI:
    @pytest.fixture()
    def projects_file(self, tmp_path):
        data = {
            "projects": [
                {
                    "slug": "alpha-proj",
                    "project_name": "Alpha Project",
                    "category": "engineering",
                    "status": "in_progress",
                    "priority": "high",
                    "owner": "eng-lead",
                },
            ],
            "last_updated": "2026-01-01",
        }
        path = tmp_path / "projects.json"
        path.write_text(json.dumps(data, indent=2))
        return path

    def test_set_updates_project_field(self, projects_file):
        """--set status=blocked updates the project record."""
        rc, out, err = run_cli(UPSERT_PROJECT_SCRIPT, [
            "--file", str(projects_file),
            "--slug", "alpha-proj",
            "--set", "status=blocked",
        ])
        assert rc == 0, err
        updated = json.loads(projects_file.read_text())
        proj = updated["projects"][0]
        assert proj["status"] == "blocked"

    def test_nonexistent_slug_exits_nonzero(self, projects_file):
        """Upserting a slug that doesn't exist produces a non-zero exit."""
        rc, out, err = run_cli(UPSERT_PROJECT_SCRIPT, [
            "--file", str(projects_file),
            "--slug", "no-such-project",
            "--set", "status=active",
        ])
        assert rc != 0


# ── render_project_dashboard: build_dashboard ────────────────────────────

class TestProjectBuildDashboard:
    def _make_registry(self, projects):
        return {
            "fund_name": "TestFund",
            "last_updated": "2026-03-10",
            "projects": projects,
        }

    def test_projects_dashboard_markdown(self):
        """Dashboard contains status counts and category counts."""
        projects = [
            {"slug": "p1", "project_name": "P1", "category": "ops", "status": "in_progress",
             "priority": "high", "owner": "alice", "target_date": "2026-06-01"},
            {"slug": "p2", "project_name": "P2", "category": "ops", "status": "in_progress",
             "priority": "medium", "owner": "bob", "target_date": "2026-07-01"},
            {"slug": "p3", "project_name": "P3", "category": "hiring", "status": "planned",
             "priority": "low", "owner": "carol", "target_date": "2026-08-01"},
        ]
        md = pm_build_dashboard(self._make_registry(projects))
        assert "# Project Dashboard" in md
        assert "Total projects: `3`" in md

    def test_empty_projects_header_only(self):
        """Empty project list still produces the dashboard header."""
        md = pm_build_dashboard(self._make_registry([]))
        assert "# Project Dashboard" in md
        assert "Total projects: `0`" in md

    def test_status_counts_section(self):
        """Status counts section shows correct tallies."""
        projects = [
            {"slug": "a", "project_name": "A", "category": "ops", "status": "in_progress"},
            {"slug": "b", "project_name": "B", "category": "ops", "status": "in_progress"},
            {"slug": "c", "project_name": "C", "category": "eng", "status": "planned"},
        ]
        md = pm_build_dashboard(self._make_registry(projects))
        assert "`in_progress`: `2`" in md
        assert "`planned`: `1`" in md

    def test_category_counts_section(self):
        """Category counts section shows correct tallies."""
        projects = [
            {"slug": "a", "project_name": "A", "category": "ops", "status": "in_progress"},
            {"slug": "b", "project_name": "B", "category": "ops", "status": "in_progress"},
            {"slug": "c", "project_name": "C", "category": "eng", "status": "planned"},
        ]
        md = pm_build_dashboard(self._make_registry(projects))
        assert "`ops`: `2`" in md
        assert "`eng`: `1`" in md


# ── render_project_dashboard: project_row ────────────────────────────────

class TestProjectRow:
    def test_all_fields(self):
        """project_row formats a complete record into a markdown table row."""
        proj = {
            "project_name": "Fund Ops",
            "category": "operations",
            "status": "in_progress",
            "priority": "high",
            "owner": "alice",
            "target_date": "2026-06-01",
            "next_action_due": "2026-04-01",
            "next_action": "Review budget",
        }
        row = project_row(proj)
        assert "| Fund Ops |" in row
        assert "operations" in row
        assert "in_progress" in row
        assert "high" in row
        assert "alice" in row
        assert "2026-06-01" in row
        assert "2026-04-01" in row
        assert "Review budget" in row

    def test_blockers_as_string_in_dashboard(self):
        """Blockers given as plain strings render correctly in detailed notes."""
        projects = [
            {
                "slug": "bp",
                "project_name": "Blocked Project",
                "category": "eng",
                "status": "blocked",
                "priority": "high",
                "owner": "dev",
                "blockers": ["Waiting on vendor", "Need approval"],
            },
        ]
        registry = {"fund_name": "F", "last_updated": "2026-03-10", "projects": projects}
        md = pm_build_dashboard(registry)
        assert "Waiting on vendor" in md
        assert "Need approval" in md

    def test_blockers_as_dict_list_in_dashboard(self):
        """Blockers given as dicts render with description and owner."""
        projects = [
            {
                "slug": "dp",
                "project_name": "Dict Blockers",
                "category": "eng",
                "status": "blocked",
                "priority": "high",
                "owner": "dev",
                "blockers": [
                    {"description": "API dependency", "owner": "backend-team"},
                ],
            },
        ]
        registry = {"fund_name": "F", "last_updated": "2026-03-10", "projects": projects}
        md = pm_build_dashboard(registry)
        assert "API dependency" in md
        assert "backend-team" in md
