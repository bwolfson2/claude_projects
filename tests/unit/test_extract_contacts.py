"""
Tests for extract_contacts.py — parse helpers and contact extraction.

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
    if (_p / "skills" / "crm-contacts" / "scripts" / "extract_contacts.py").exists():
        break
    _p = _p.parent
REPO_ROOT = _p

SCRIPTS_DIR = REPO_ROOT / "skills" / "crm-contacts" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from extract_contacts import parse_email_name, domain_to_company, extract_contacts

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
    """Create an in-memory DB with the full schema."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def _insert_message(conn, *, source="outlook", source_id=None, sender=None,
                    recipients=None, timestamp="2025-01-15T10:00:00",
                    project_tags="[]", **kw):
    """Helper to insert a message row."""
    source_id = source_id or f"msg-{id(sender)}"
    conn.execute(
        """INSERT INTO messages (source, source_id, type, sender, recipients,
            subject, body, timestamp, project_tags)
           VALUES (?, ?, 'email', ?, ?, 'subj', 'body', ?, ?)""",
        (source, source_id, sender, recipients, timestamp, project_tags),
    )
    conn.commit()


# ── parse_email_name tests ────────────────────────────────────────────────

class TestParseEmailName:
    def test_name_angle_bracket_format(self):
        name, email = parse_email_name("Jane Smith <jane@co.com>")
        assert name == "Jane Smith"
        assert email == "jane@co.com"

    def test_bare_email(self):
        name, email = parse_email_name("jane@co.com")
        assert email == "jane@co.com"
        assert name == "Jane"

    def test_empty_string(self):
        name, email = parse_email_name("")
        assert name == ""
        assert email == ""

    def test_bare_name_handle(self):
        name, email = parse_email_name("janesmith")
        assert name == "janesmith"
        assert email == ""


# ── domain_to_company tests ──────────────────────────────────────────────

class TestDomainToCompany:
    def test_corporate_domain(self):
        assert domain_to_company("jane@acme.com") == "Acme"

    def test_generic_gmail(self):
        assert domain_to_company("jane@gmail.com") == ""

    def test_generic_yahoo(self):
        assert domain_to_company("bob@yahoo.com") == ""

    def test_empty_string(self):
        assert domain_to_company("") == ""

    def test_no_at_sign(self):
        assert domain_to_company("noemail") == ""


# ── extract_contacts tests ───────────────────────────────────────────────

class TestExtractContacts:
    def test_empty_db_returns_zero(self):
        conn = _fresh_db()
        stats = extract_contacts(conn)
        assert stats["messages_scanned"] == 0
        assert stats["contacts_found"] == 0

    def test_three_messages_creates_contacts(self):
        conn = _fresh_db()
        _insert_message(conn, source_id="m1", sender="Alice <alice@acme.com>")
        _insert_message(conn, source_id="m2", sender="Bob <bob@widgets.io>")
        _insert_message(conn, source_id="m3", sender="Carol <carol@bigco.org>")
        stats = extract_contacts(conn)
        assert stats["messages_scanned"] == 3
        assert stats["contacts_found"] == 3
        assert stats["new"] == 3

    def test_duplicate_emails_dedup(self):
        conn = _fresh_db()
        _insert_message(conn, source_id="m1", sender="Alice <alice@acme.com>",
                        timestamp="2025-01-10T10:00:00")
        _insert_message(conn, source_id="m2", sender="Alice Smith <alice@acme.com>",
                        timestamp="2025-01-15T10:00:00")
        stats = extract_contacts(conn)
        assert stats["contacts_found"] == 1
        assert stats["new"] == 1

    def test_source_filter(self):
        conn = _fresh_db()
        _insert_message(conn, source="outlook", source_id="m1",
                        sender="Alice <alice@acme.com>")
        _insert_message(conn, source="slack", source_id="m2",
                        sender="Bob <bob@widgets.io>")
        stats = extract_contacts(conn, source_filter="outlook")
        assert stats["messages_scanned"] == 1
        assert stats["contacts_found"] == 1

    def test_dry_run_no_db_writes(self):
        conn = _fresh_db()
        _insert_message(conn, source_id="m1", sender="Alice <alice@acme.com>")
        stats = extract_contacts(conn, dry_run=True)
        assert stats["contacts_found"] == 1
        row = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        assert row == 0

    def test_recipients_json_array(self):
        conn = _fresh_db()
        recips = json.dumps(["Bob <bob@widgets.io>", "carol@bigco.org"])
        _insert_message(conn, source_id="m1", sender="Alice <alice@acme.com>",
                        recipients=recips)
        stats = extract_contacts(conn)
        # sender + 2 recipients = 3 contacts
        assert stats["contacts_found"] == 3

    def test_project_tags_populate_deal_slugs(self):
        conn = _fresh_db()
        tags = json.dumps(["deal-alpha", "deal-beta"])
        _insert_message(conn, source_id="m1", sender="Alice <alice@acme.com>",
                        project_tags=tags)
        stats = extract_contacts(conn)
        assert stats["new"] == 1
        row = conn.execute("SELECT deal_slugs FROM contacts WHERE email = ?",
                           ("alice@acme.com",)).fetchone()
        slugs = json.loads(row[0])
        assert "deal-alpha" in slugs
        assert "deal-beta" in slugs

    def test_malformed_recipients_json_graceful(self):
        conn = _fresh_db()
        _insert_message(conn, source_id="m1", sender="Alice <alice@acme.com>",
                        recipients="not-valid-json{{{")
        # Should not raise — falls back to comma-split
        stats = extract_contacts(conn)
        assert stats["messages_scanned"] == 1
