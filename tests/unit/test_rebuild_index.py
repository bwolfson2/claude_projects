"""
Tests for rebuild_index.py — Index Builder

Tests rebuilding company_index and project_index from JSON files.
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "fund" / "metadata"))
from rebuild_index import rebuild_company_index, rebuild_project_index, slugify, extract_domain


class TestRebuildCompanyIndex:

    @pytest.fixture(autouse=True)
    def setup(self, fresh_db, tmp_path):
        self.conn, self.db_path = fresh_db
        self.tmp = tmp_path

    def _write_deals(self, data):
        path = self.tmp / "deals.json"
        path.write_text(json.dumps(data, indent=2))
        return str(path)

    def test_basic_rebuild_3_companies(self):
        path = self._write_deals({
            "companies": [
                {"slug": "alpha", "company_name": "Alpha Inc", "status": "active"},
                {"slug": "beta", "company_name": "Beta Co", "status": "active"},
                {"slug": "gamma", "company_name": "Gamma Ltd", "status": "active"},
            ]
        })
        rebuild_company_index(self.conn, path)
        self.conn.commit()
        count = self.conn.execute("SELECT COUNT(*) FROM company_index").fetchone()[0]
        assert count == 3

    def test_clears_old_data_on_rebuild(self):
        path = self._write_deals({"companies": [
            {"slug": "a", "company_name": "A"},
        ]})
        rebuild_company_index(self.conn, path)
        self.conn.commit()
        # Rebuild with different data
        path2 = self._write_deals({"companies": [
            {"slug": "b", "company_name": "B"},
        ]})
        rebuild_company_index(self.conn, str(Path(path2)))
        self.conn.commit()
        rows = self.conn.execute("SELECT company_slug FROM company_index").fetchall()
        slugs = [r[0] for r in rows]
        assert "b" in slugs
        assert "a" not in slugs

    def test_domains_from_explicit_and_contacts(self):
        path = self._write_deals({"companies": [
            {"slug": "alpha", "company_name": "Alpha",
             "domains": ["alpha.io"],
             "contact_emails": ["ceo@alpha.com"]},
        ]})
        rebuild_company_index(self.conn, path)
        self.conn.commit()
        row = self.conn.execute("SELECT domains FROM company_index WHERE company_slug='alpha'").fetchone()
        domains = row[0].split(",")
        assert "alpha.io" in domains
        assert "alpha.com" in domains

    def test_auto_inferred_domain(self):
        """slug.com is automatically added to domains."""
        path = self._write_deals({"companies": [
            {"slug": "myco", "company_name": "MyCo"},
        ]})
        rebuild_company_index(self.conn, path)
        self.conn.commit()
        row = self.conn.execute("SELECT domains FROM company_index WHERE company_slug='myco'").fetchone()
        assert "myco.com" in row[0]

    def test_keywords_from_name_sector(self):
        path = self._write_deals({"companies": [
            {"slug": "finco", "company_name": "FinCo Technologies", "sector": "Fintech SaaS"},
        ]})
        rebuild_company_index(self.conn, path)
        self.conn.commit()
        row = self.conn.execute("SELECT keywords FROM company_index WHERE company_slug='finco'").fetchone()
        kw = row[0].lower()
        assert "finco" in kw
        assert "fintech" in kw
        assert "saas" in kw
        assert "technologies" in kw

    def test_empty_companies_array(self):
        path = self._write_deals({"companies": []})
        rebuild_company_index(self.conn, path)
        self.conn.commit()
        count = self.conn.execute("SELECT COUNT(*) FROM company_index").fetchone()[0]
        assert count == 0

    def test_missing_slug_key_raises(self):
        path = self._write_deals({"companies": [
            {"company_name": "NoSlug Inc"},
        ]})
        with pytest.raises(KeyError):
            rebuild_company_index(self.conn, path)

    def test_unicode_company_name_keywords(self):
        path = self._write_deals({"companies": [
            {"slug": "uni-co", "company_name": "Ünternéhmen GmbH"},
        ]})
        rebuild_company_index(self.conn, path)
        self.conn.commit()
        row = self.conn.execute("SELECT keywords FROM company_index WHERE company_slug='uni-co'").fetchone()
        assert row is not None

    def test_empty_contact_emails(self):
        path = self._write_deals({"companies": [
            {"slug": "noemail", "company_name": "NoEmail Co"},
        ]})
        rebuild_company_index(self.conn, path)
        self.conn.commit()
        row = self.conn.execute("SELECT contact_emails FROM company_index WHERE company_slug='noemail'").fetchone()
        assert row[0] == ""

    def test_extra_json_fields_ignored(self):
        path = self._write_deals({"companies": [
            {"slug": "extra", "company_name": "Extra Co",
             "random_field": "should not crash", "nested": {"deep": True}},
        ]})
        rebuild_company_index(self.conn, path)
        self.conn.commit()
        count = self.conn.execute("SELECT COUNT(*) FROM company_index").fetchone()[0]
        assert count == 1

    def test_format_mismatch_flat_array(self):
        """classify_messages.py auto-create writes [{}] but rebuild expects {companies: [{}]}."""
        path = self._write_deals([
            {"slug": "flat", "company_name": "Flat Co"},
        ])
        rebuild_company_index(self.conn, path)
        self.conn.commit()
        count = self.conn.execute("SELECT COUNT(*) FROM company_index").fetchone()[0]
        assert count == 1


class TestRebuildProjectIndex:

    @pytest.fixture(autouse=True)
    def setup(self, fresh_db, tmp_path):
        self.conn, self.db_path = fresh_db
        self.tmp = tmp_path

    def _write_projects(self, data):
        path = self.tmp / "projects.json"
        path.write_text(json.dumps(data, indent=2))
        return str(path)

    def test_basic_rebuild(self):
        path = self._write_projects({"projects": [
            {"slug": "proj-a", "project_name": "Project A", "status": "active"},
            {"slug": "proj-b", "project_name": "Project B", "status": "active"},
        ]})
        rebuild_project_index(self.conn, path)
        self.conn.commit()
        count = self.conn.execute("SELECT COUNT(*) FROM project_index").fetchone()[0]
        assert count == 2

    def test_category_keywords(self):
        path = self._write_projects({"projects": [
            {"slug": "hiring", "project_name": "Eng Hiring",
             "category": "recruitment ops"},
        ]})
        rebuild_project_index(self.conn, path)
        self.conn.commit()
        row = self.conn.execute("SELECT keywords FROM project_index WHERE project_slug='hiring'").fetchone()
        kw = row[0].lower()
        assert "recruitment" in kw
        assert "ops" in kw


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        result = slugify("Test!@#$%^Value")
        assert "test" in result
        assert "value" in result


class TestExtractDomain:
    def test_normal_email(self):
        assert extract_domain("user@example.com") == "example.com"

    def test_no_at_sign(self):
        assert extract_domain("nodomain") == "nodomain"
