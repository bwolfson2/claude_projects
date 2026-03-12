"""
Tests for fund-dealflow-orchestrator scripts:
  - upsert_deal.py (parse_value, set_path, append_path, CLI)
  - render_dealflow_dashboard.py (build_dashboard, company_row)
  - init_company_workspace.py (workspace creation, registry entry)
"""

import json
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT, run_cli

# ── Direct imports for unit-level tests ──────────────────────────────────

sys.path.insert(0, str(REPO_ROOT / "skills" / "fund-dealflow-orchestrator" / "scripts"))
from upsert_deal import parse_value, set_path, append_path
from render_dealflow_dashboard import build_dashboard, company_row

# ── Script paths ─────────────────────────────────────────────────────────

UPSERT_DEAL_SCRIPT = REPO_ROOT / "skills" / "fund-dealflow-orchestrator" / "scripts" / "upsert_deal.py"
RENDER_DASHBOARD_SCRIPT = REPO_ROOT / "skills" / "fund-dealflow-orchestrator" / "scripts" / "render_dealflow_dashboard.py"
INIT_WORKSPACE_SCRIPT = REPO_ROOT / "skills" / "fund-dealflow-orchestrator" / "scripts" / "init_company_workspace.py"


# ── upsert_deal: parse_value ─────────────────────────────────────────────

class TestParseValue:
    def test_json_string_parsed(self):
        """JSON-encoded string is deserialized."""
        assert parse_value('["a", "b"]') == ["a", "b"]

    def test_plain_string_returned_as_is(self):
        """Non-JSON string comes back unchanged."""
        assert parse_value("hello world") == "hello world"

    def test_json_number(self):
        assert parse_value("42") == 42

    def test_json_bool(self):
        assert parse_value("true") is True


# ── upsert_deal: set_path / append_path ──────────────────────────────────

class TestSetPath:
    def test_dotted_key_updates_nested(self):
        """Dotted key like 'a.b' sets nested dict value."""
        obj = {"a": {"b": "old"}}
        set_path(obj, "a.b", "new")
        assert obj["a"]["b"] == "new"

    def test_creates_intermediate_dicts(self):
        """Missing intermediate keys are created as empty dicts."""
        obj = {}
        set_path(obj, "x.y.z", 99)
        assert obj == {"x": {"y": {"z": 99}}}


class TestAppendPath:
    def test_append_to_existing_list(self):
        obj = {"tags": ["a"]}
        append_path(obj, "tags", "b")
        assert obj["tags"] == ["a", "b"]

    def test_append_creates_list_if_missing(self):
        obj = {}
        append_path(obj, "items", "first")
        assert obj["items"] == ["first"]

    def test_append_raises_on_non_list(self):
        obj = {"val": "string"}
        with pytest.raises(TypeError):
            append_path(obj, "val", "x")


# ── upsert_deal: CLI ─────────────────────────────────────────────────────

class TestUpsertDealCLI:
    @pytest.fixture()
    def deals_file(self, tmp_path):
        data = {
            "companies": [
                {"slug": "alpha", "company_name": "Alpha Inc", "stage": "sourced", "status": "active"},
            ],
            "last_updated": "2026-01-01",
        }
        path = tmp_path / "deals.json"
        path.write_text(json.dumps(data, indent=2))
        return path

    def test_set_updates_existing_field(self, deals_file):
        """--set stage=diligence updates the company record."""
        rc, out, err = run_cli(UPSERT_DEAL_SCRIPT, [
            "--file", str(deals_file),
            "--slug", "alpha",
            "--set", "stage=diligence",
        ])
        assert rc == 0, err
        updated = json.loads(deals_file.read_text())
        company = updated["companies"][0]
        assert company["stage"] == "diligence"

    def test_nonexistent_slug_exits_nonzero(self, deals_file):
        """Upserting a slug that doesn't exist produces a non-zero exit."""
        rc, out, err = run_cli(UPSERT_DEAL_SCRIPT, [
            "--file", str(deals_file),
            "--slug", "does-not-exist",
            "--set", "stage=sourced",
        ])
        assert rc != 0


# ── render_dealflow_dashboard: build_dashboard ───────────────────────────

class TestBuildDashboard:
    def _make_registry(self, companies):
        return {
            "fund_name": "TestFund",
            "last_updated": "2026-03-10",
            "companies": companies,
        }

    def test_three_companies_stage_counts(self):
        """Dashboard markdown contains stage count lines for each distinct stage."""
        companies = [
            {"slug": "a", "company_name": "A Co", "stage": "sourced", "status": "active",
             "decision_posture": "open", "owner": "me"},
            {"slug": "b", "company_name": "B Co", "stage": "sourced", "status": "active",
             "decision_posture": "open", "owner": "me"},
            {"slug": "c", "company_name": "C Co", "stage": "diligence", "status": "active",
             "decision_posture": "open", "owner": "me"},
        ]
        md = build_dashboard(self._make_registry(companies))
        assert "Total companies: `3`" in md
        assert "`sourced`: `2`" in md
        assert "`diligence`: `1`" in md

    def test_empty_registry_header_only(self):
        """Empty company list still produces the dashboard header."""
        md = build_dashboard(self._make_registry([]))
        assert "# Fund Dashboard" in md
        assert "Total companies: `0`" in md
        # No stage count lines
        assert "## Stage Counts" in md


class TestCompanyRow:
    def test_formats_correctly(self):
        company = {
            "company_name": "Acme",
            "stage": "IC",
            "decision_posture": "open",
            "raise_usd": 5_000_000,
            "valuation_cap_usd": 20_000_000,
            "owner": "gp1",
            "next_action_due": "2026-04-01",
            "next_action": "Send term sheet",
        }
        row = company_row(company)
        assert "| Acme |" in row
        assert "IC" in row
        assert "$5,000,000" in row
        assert "$20,000,000" in row
        assert "gp1" in row
        assert "Send term sheet" in row


# ── init_company_workspace: CLI ──────────────────────────────────────────

class TestInitCompanyWorkspace:
    @pytest.fixture()
    def workspace_root(self, tmp_path):
        """Set up a minimal repo-like structure with template assets."""
        assets_dir = tmp_path / "skills" / "fund-dealflow-orchestrator" / "assets"
        assets_dir.mkdir(parents=True)
        (assets_dir / "company-record-template.md").write_text("# {{company_name}}\n")
        (assets_dir / "next-actions-template.md").write_text("# Next Actions\n")
        (assets_dir / "ic-snapshot-template.md").write_text("# IC Snapshot\n")
        return tmp_path

    def test_creates_directory_structure(self, workspace_root):
        """init_company_workspace creates company dir with expected files."""
        rc, out, err = run_cli(INIT_WORKSPACE_SCRIPT, [
            "--name", "TestCo",
            "--slug", "testco",
            "--fund-root", "fund",
        ], env_override={"PWD": str(workspace_root)})
        # The script uses Path.cwd(), so we run it with cwd set
        import subprocess, sys as _sys, os
        env = os.environ.copy()
        result = subprocess.run(
            [_sys.executable, str(INIT_WORKSPACE_SCRIPT),
             "--name", "TestCo", "--slug", "testco", "--fund-root", "fund"],
            capture_output=True, text=True, env=env, cwd=str(workspace_root), timeout=30,
        )
        assert result.returncode == 0, result.stderr

        company_dir = workspace_root / "fund" / "companies" / "testco"
        assert (company_dir / "company.md").exists()
        assert (company_dir / "next-actions.md").exists()
        assert (company_dir / "diligence" / "ic-snapshot.md").exists()
        assert (company_dir / "meetings" / "notes.md").exists()
        # Template substitution worked
        assert "# TestCo" in (company_dir / "company.md").read_text()

    def test_adds_entry_to_deals_json(self, workspace_root):
        """init_company_workspace creates an entry in fund/crm/deals.json."""
        import subprocess, sys as _sys, os
        env = os.environ.copy()
        result = subprocess.run(
            [_sys.executable, str(INIT_WORKSPACE_SCRIPT),
             "--name", "NewDeal", "--slug", "newdeal", "--fund-root", "fund",
             "--stage", "sourced", "--owner", "gp1"],
            capture_output=True, text=True, env=env, cwd=str(workspace_root), timeout=30,
        )
        assert result.returncode == 0, result.stderr

        registry = json.loads(
            (workspace_root / "fund" / "crm" / "deals.json").read_text()
        )
        slugs = [c["slug"] for c in registry["companies"]]
        assert "newdeal" in slugs
        record = next(c for c in registry["companies"] if c["slug"] == "newdeal")
        assert record["company_name"] == "NewDeal"
        assert record["stage"] == "sourced"
        assert record["owner"] == "gp1"
