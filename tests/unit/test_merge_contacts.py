"""
Tests for merge_contacts.py — find merge candidates and merge pairs.

Self-contained: creates the DB schema inline so tests work in worktrees.
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
    if (_p / "skills" / "crm-contacts" / "scripts" / "merge_contacts.py").exists():
        break
    _p = _p.parent
REPO_ROOT = _p

SCRIPTS_DIR = REPO_ROOT / "skills" / "crm-contacts" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from merge_contacts import find_merge_candidates, merge_pair

# ── Inline Schema ─────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL CHECK(source IN ('outlook','slack','whatsapp','signal','granola','web')),
    source_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('email','message','transcript','thread','document','scrape')),
    sender TEXT, recipients TEXT, subject TEXT, body TEXT,
    timestamp TEXT, channel TEXT, attachments TEXT DEFAULT '[]',
    project_tags TEXT DEFAULT '[]', raw_path TEXT, metadata TEXT DEFAULT '{}',
    classified INTEGER DEFAULT 0, routed_at TEXT, created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source, source_id)
);
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, email TEXT UNIQUE, phone TEXT, company TEXT,
    title TEXT, slack_handle TEXT, whatsapp_id TEXT, signal_id TEXT,
    linkedin_url TEXT, tags TEXT DEFAULT '[]', context TEXT,
    deal_slugs TEXT DEFAULT '[]', project_slugs TEXT DEFAULT '[]',
    first_seen TEXT, last_contacted TEXT, source TEXT,
    metadata TEXT DEFAULT '{}', created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS classification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL, source_id INTEGER NOT NULL,
    matched_slug TEXT, match_type TEXT CHECK(match_type IN ('deal','project','both','none')),
    confidence REAL DEFAULT 0.0, rule_hits TEXT DEFAULT '{}',
    reasoning TEXT, reviewed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def _fresh_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def _insert_contact(conn, *, name, email=None, phone=None, company=None,
                    title=None, slack_handle=None, tags="[]",
                    deal_slugs="[]", project_slugs="[]",
                    first_seen=None, last_contacted=None, source=None):
    conn.execute(
        """INSERT INTO contacts (name, email, phone, company, title,
            slack_handle, tags, deal_slugs, project_slugs,
            first_seen, last_contacted, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, email, phone, company, title, slack_handle, tags,
         deal_slugs, project_slugs, first_seen, last_contacted, source),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── find_merge_candidates tests ──────────────────────────────────────────

class TestFindMergeCandidates:
    def test_no_duplicates_empty(self):
        conn = _fresh_db()
        _insert_contact(conn, name="Alice", email="alice@acme.com", company="Acme")
        _insert_contact(conn, name="Bob", email="bob@widgets.io", company="Widgets")
        candidates = find_merge_candidates(conn)
        assert candidates == []

    def test_same_name_and_company(self):
        conn = _fresh_db()
        _insert_contact(conn, name="Alice", email="alice@acme.com", company="Acme")
        _insert_contact(conn, name="Alice", email="alice2@acme.com", company="Acme")
        candidates = find_merge_candidates(conn)
        assert len(candidates) == 1
        assert "same name+company" in candidates[0][2]

    def test_case_insensitive_name_match(self):
        conn = _fresh_db()
        _insert_contact(conn, name="alice", email="a1@acme.com", company="acme")
        _insert_contact(conn, name="Alice", email="a2@acme.com", company="Acme")
        candidates = find_merge_candidates(conn)
        assert len(candidates) == 1

    def test_same_phone_different_formats(self):
        conn = _fresh_db()
        _insert_contact(conn, name="Alice", email="a1@acme.com", phone="+1-555-123-4567")
        _insert_contact(conn, name="Alice W", email="a2@other.com", phone="15551234567")
        candidates = find_merge_candidates(conn)
        assert len(candidates) == 1
        assert "same phone" in candidates[0][2]


# ── merge_pair tests ─────────────────────────────────────────────────────

class TestMergePair:
    def test_fills_blank_fields(self):
        conn = _fresh_db()
        kid = _insert_contact(conn, name="Alice", email="alice@acme.com",
                              company="Acme", title=None, slack_handle=None)
        mid = _insert_contact(conn, name="Alice", email="alice2@acme.com",
                              company="Acme", title="VP", slack_handle="@alice")
        merge_pair(conn, kid, mid)
        row = dict(conn.execute("SELECT * FROM contacts WHERE id = ?", (kid,)).fetchone())
        assert row["title"] == "VP"
        assert row["slack_handle"] == "@alice"

    def test_combines_json_arrays(self):
        conn = _fresh_db()
        kid = _insert_contact(conn, name="Alice", email="a1@acme.com",
                              tags='["vip"]', deal_slugs='["deal-a"]')
        mid = _insert_contact(conn, name="Alice", email="a2@acme.com",
                              tags='["investor"]', deal_slugs='["deal-b"]')
        merge_pair(conn, kid, mid)
        row = dict(conn.execute("SELECT * FROM contacts WHERE id = ?", (kid,)).fetchone())
        tags = json.loads(row["tags"])
        assert "vip" in tags
        assert "investor" in tags
        slugs = json.loads(row["deal_slugs"])
        assert "deal-a" in slugs
        assert "deal-b" in slugs

    def test_uses_earlier_first_seen(self):
        conn = _fresh_db()
        kid = _insert_contact(conn, name="Alice", email="a1@acme.com",
                              first_seen="2025-03-01")
        mid = _insert_contact(conn, name="Alice", email="a2@acme.com",
                              first_seen="2025-01-01")
        merge_pair(conn, kid, mid)
        row = dict(conn.execute("SELECT * FROM contacts WHERE id = ?", (kid,)).fetchone())
        assert row["first_seen"] == "2025-01-01"

    def test_uses_later_last_contacted(self):
        conn = _fresh_db()
        kid = _insert_contact(conn, name="Alice", email="a1@acme.com",
                              last_contacted="2025-01-01")
        mid = _insert_contact(conn, name="Alice", email="a2@acme.com",
                              last_contacted="2025-06-01")
        merge_pair(conn, kid, mid)
        row = dict(conn.execute("SELECT * FROM contacts WHERE id = ?", (kid,)).fetchone())
        assert row["last_contacted"] == "2025-06-01"

    def test_deletes_merge_record(self):
        conn = _fresh_db()
        kid = _insert_contact(conn, name="Alice", email="a1@acme.com", company="Acme")
        mid = _insert_contact(conn, name="Alice", email="a2@acme.com", company="Acme")
        merge_pair(conn, kid, mid)
        gone = conn.execute("SELECT * FROM contacts WHERE id = ?", (mid,)).fetchone()
        assert gone is None

    def test_dry_run_no_changes(self):
        """Simulate dry-run: find candidates but don't call merge_pair."""
        conn = _fresh_db()
        _insert_contact(conn, name="Alice", email="a1@acme.com", company="Acme")
        _insert_contact(conn, name="Alice", email="a2@acme.com", company="Acme")
        candidates = find_merge_candidates(conn)
        assert len(candidates) == 1
        # Don't call merge_pair — verify both records still exist
        count = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        assert count == 2
