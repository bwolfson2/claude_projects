"""
Tests for sync_contacts.py — export contacts to JSON.

Self-contained: creates the DB schema inline so tests work in worktrees.
Monkeypatches DB_PATH and CONTACTS_JSON module-level variables.
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

# ── Paths ─────────────────────────────────────────────────────────────────
REPO_ROOT = Path("/Users/nebnoseflow/due_diligences")
_p = REPO_ROOT
while _p != _p.parent:
    if (_p / "skills" / "crm-contacts" / "scripts" / "sync_contacts.py").exists():
        break
    _p = _p.parent
REPO_ROOT = _p

SCRIPTS_DIR = REPO_ROOT / "skills" / "crm-contacts" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sync_contacts

# ── Inline Schema ─────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, email TEXT UNIQUE, phone TEXT, company TEXT,
    title TEXT, slack_handle TEXT, whatsapp_id TEXT, signal_id TEXT,
    linkedin_url TEXT, tags TEXT DEFAULT '[]', context TEXT,
    deal_slugs TEXT DEFAULT '[]', project_slugs TEXT DEFAULT '[]',
    first_seen TEXT, last_contacted TEXT, source TEXT,
    metadata TEXT DEFAULT '{}', created_at TEXT DEFAULT (datetime('now'))
);
"""


def _make_db(tmp_path):
    """Create a real on-disk DB so DB_PATH.exists() passes."""
    db_path = tmp_path / "ingestion.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA)
    conn.close()
    return db_path


def _insert_contact(db_path, *, name, email=None, phone=None, company=None,
                    tags="[]", deal_slugs="[]", project_slugs="[]",
                    first_seen=None, last_contacted=None, source=None):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT INTO contacts (name, email, phone, company, tags,
            deal_slugs, project_slugs, first_seen, last_contacted, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, email, phone, company, tags, deal_slugs, project_slugs,
         first_seen, last_contacted, source),
    )
    conn.commit()
    conn.close()


# ── Tests ─────────────────────────────────────────────────────────────────

class TestExportContacts:
    def test_exports_three_contacts(self, tmp_path, monkeypatch):
        db_path = _make_db(tmp_path)
        json_path = tmp_path / "crm" / "contacts.json"
        monkeypatch.setattr(sync_contacts, "DB_PATH", db_path)
        monkeypatch.setattr(sync_contacts, "CONTACTS_JSON", json_path)

        _insert_contact(db_path, name="Alice", email="alice@acme.com")
        _insert_contact(db_path, name="Bob", email="bob@widgets.io")
        _insert_contact(db_path, name="Carol", email="carol@bigco.org")

        sync_contacts.export_contacts()
        data = json.loads(json_path.read_text())
        assert len(data) == 3

    def test_empty_table_exports_empty_array(self, tmp_path, monkeypatch):
        db_path = _make_db(tmp_path)
        json_path = tmp_path / "contacts.json"
        monkeypatch.setattr(sync_contacts, "DB_PATH", db_path)
        monkeypatch.setattr(sync_contacts, "CONTACTS_JSON", json_path)

        sync_contacts.export_contacts()
        data = json.loads(json_path.read_text())
        assert data == []

    def test_json_fields_parsed_as_lists(self, tmp_path, monkeypatch):
        db_path = _make_db(tmp_path)
        json_path = tmp_path / "contacts.json"
        monkeypatch.setattr(sync_contacts, "DB_PATH", db_path)
        monkeypatch.setattr(sync_contacts, "CONTACTS_JSON", json_path)

        _insert_contact(db_path, name="Alice", email="alice@acme.com",
                        tags='["vip","investor"]', deal_slugs='["deal-a"]')

        sync_contacts.export_contacts()
        data = json.loads(json_path.read_text())
        assert isinstance(data[0]["tags"], list)
        assert data[0]["tags"] == ["vip", "investor"]
        assert data[0]["deal_slugs"] == ["deal-a"]

    def test_ordered_by_last_contacted_desc(self, tmp_path, monkeypatch):
        db_path = _make_db(tmp_path)
        json_path = tmp_path / "contacts.json"
        monkeypatch.setattr(sync_contacts, "DB_PATH", db_path)
        monkeypatch.setattr(sync_contacts, "CONTACTS_JSON", json_path)

        _insert_contact(db_path, name="Old", email="old@x.com",
                        last_contacted="2024-01-01")
        _insert_contact(db_path, name="Recent", email="new@x.com",
                        last_contacted="2025-06-01")
        _insert_contact(db_path, name="Mid", email="mid@x.com",
                        last_contacted="2025-03-01")

        sync_contacts.export_contacts()
        data = json.loads(json_path.read_text())
        names = [c["name"] for c in data]
        assert names == ["Recent", "Mid", "Old"]

    def test_creates_parent_directory(self, tmp_path, monkeypatch):
        db_path = _make_db(tmp_path)
        json_path = tmp_path / "deep" / "nested" / "dir" / "contacts.json"
        monkeypatch.setattr(sync_contacts, "DB_PATH", db_path)
        monkeypatch.setattr(sync_contacts, "CONTACTS_JSON", json_path)

        _insert_contact(db_path, name="Alice", email="alice@acme.com")

        sync_contacts.export_contacts()
        assert json_path.exists()

    def test_null_json_fields_default_to_empty_list(self, tmp_path, monkeypatch):
        db_path = _make_db(tmp_path)
        json_path = tmp_path / "contacts.json"
        monkeypatch.setattr(sync_contacts, "DB_PATH", db_path)
        monkeypatch.setattr(sync_contacts, "CONTACTS_JSON", json_path)

        # Insert with NULL tags (bypass default by explicit NULL)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """INSERT INTO contacts (name, email, tags, deal_slugs, project_slugs)
               VALUES ('Alice', 'alice@acme.com', NULL, 'not-valid-json{', NULL)""")
        conn.commit()
        conn.close()

        sync_contacts.export_contacts()
        data = json.loads(json_path.read_text())
        assert data[0]["tags"] == []
        assert data[0]["deal_slugs"] == []
        assert data[0]["project_slugs"] == []
