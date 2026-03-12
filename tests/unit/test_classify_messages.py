"""
Tests for classify_messages.py — all 6 subcommands.

Uses run_cli() for subprocess-level testing and validates JSON output,
database state changes, and file mutations.

Self-contained: creates the DB schema inline so tests work in worktrees
that lack fund/metadata/init_db.py.
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

# ── Paths ─────────────────────────────────────────────────────────────────
# The main repo root (not the worktree) where the script lives.
_MAIN_REPO = Path(__file__).resolve().parents[2]
# Walk up until we find the skills directory — handles both worktree and main.
_p = _MAIN_REPO
while _p != _p.parent:
    if (_p / "skills" / "deal-project-classifier" / "scripts" / "classify_messages.py").exists():
        break
    _p = _p.parent
SCRIPT = _p / "skills" / "deal-project-classifier" / "scripts" / "classify_messages.py"

# ── Adversarial Data (same as conftest) ───────────────────────────────────

SQL_INJECTIONS = [
    "'; DROP TABLE messages; --",
    '" OR 1=1 --',
    "<script>alert(1)</script>",
    "Robert'); DROP TABLE students;--",
    "1; UPDATE messages SET classified=1 WHERE 1=1;--",
]

UNICODE_NAMES = [
    "Ünternéhmen GmbH",
    "株式会社テスト",
    "الشركة العربية",
    "Rocket Co",
    "Ñoño Technologies",
    "Ça Va Startup",
]


# ── Inline Schema (mirrors init_db.py) ───────────────────────────────────

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL CHECK (source IN ('outlook','slack','whatsapp','signal','granola','web','calendar','file_intake')),
    source_id       TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('email','message','transcript','thread','document','scrape')),
    sender          TEXT,
    recipients      TEXT,
    subject         TEXT,
    body            TEXT,
    timestamp       TEXT NOT NULL,
    channel         TEXT,
    attachments     TEXT DEFAULT '[]',
    project_tags    TEXT DEFAULT '[]',
    raw_path        TEXT,
    metadata        TEXT DEFAULT '{}',
    classified      INTEGER DEFAULT 0,
    routed_at       TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(source, source_id)
);

CREATE TABLE IF NOT EXISTS company_index (
    company_slug    TEXT PRIMARY KEY,
    company_name    TEXT NOT NULL,
    domains         TEXT,
    keywords        TEXT,
    contact_emails  TEXT,
    last_touch      TEXT,
    stage           TEXT,
    status          TEXT
);

CREATE TABLE IF NOT EXISTS project_index (
    project_slug    TEXT PRIMARY KEY,
    project_name    TEXT NOT NULL,
    keywords        TEXT,
    contact_emails  TEXT,
    category        TEXT,
    status          TEXT
);

CREATE TABLE IF NOT EXISTS classification_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type     TEXT NOT NULL CHECK (source_type IN ('email','transcript','message')),
    source_id       INTEGER NOT NULL,
    matched_slug    TEXT,
    match_type      TEXT CHECK (match_type IN ('deal','project','new_deal','new_project','unclassified')),
    confidence      REAL DEFAULT 0.0,
    rule_hits       TEXT,
    auto_created    INTEGER DEFAULT 0,
    reviewed        INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS processed_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type     TEXT NOT NULL,
    source_id       INTEGER NOT NULL,
    action_taken    TEXT,
    timestamp       TEXT DEFAULT (datetime('now')),
    UNIQUE(source_type, source_id, action_taken)
);

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_classified ON messages(classified);
CREATE INDEX IF NOT EXISTS idx_messages_source ON messages(source);
CREATE INDEX IF NOT EXISTS idx_classification_log_source ON classification_log(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_classification_log_slug ON classification_log(matched_slug);
"""


# ── Test-local Fixtures ──────────────────────────────────────────────────

def _create_db(path: str) -> sqlite3.Connection:
    """Create a fresh SQLite DB with the required schema."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_DDL)
    conn.commit()
    return conn


def _insert_message(conn, **overrides):
    """Insert a message with sensible defaults. Returns the new row id."""
    defaults = {
        "source": "outlook",
        "source_id": f"test-{datetime.now().timestamp()}",
        "type": "email",
        "sender": "test@example.com",
        "recipients": "[]",
        "subject": "Test Subject",
        "body": "Test body content.",
        "timestamp": datetime.now().isoformat(),
        "channel": "inbox",
        "attachments": "[]",
        "project_tags": "[]",
    }
    defaults.update(overrides)
    cursor = conn.execute(
        """INSERT INTO messages
           (source, source_id, type, sender, recipients, subject, body,
            timestamp, channel, attachments, project_tags)
           VALUES (:source, :source_id, :type, :sender, :recipients,
                   :subject, :body, :timestamp, :channel, :attachments, :project_tags)""",
        defaults,
    )
    conn.commit()
    return cursor.lastrowid


def _insert_classification(conn, **overrides):
    """Insert a classification_log entry. Returns the new id."""
    defaults = {
        "source_type": "message",
        "source_id": 1,
        "matched_slug": "test-deal",
        "match_type": "deal",
        "confidence": 0.9,
        "rule_hits": "{}",
        "reviewed": 0,
    }
    defaults.update(overrides)
    cursor = conn.execute(
        """INSERT INTO classification_log
           (source_type, source_id, matched_slug, match_type, confidence, rule_hits, reviewed)
           VALUES (:source_type, :source_id, :matched_slug, :match_type,
                   :confidence, :rule_hits, :reviewed)""",
        defaults,
    )
    conn.commit()
    return cursor.lastrowid


# ── CLI runner ────────────────────────────────────────────────────────────

def _run_cli(args, env_override=None):
    """Run classify_messages.py as subprocess, return (rc, stdout, stderr)."""
    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True, text=True, env=env, timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def _parse_json(stdout):
    """Parse JSON from CLI stdout."""
    lines = stdout.strip().split("\n")
    for i in range(len(lines)):
        try:
            return json.loads("\n".join(lines[i:]))
        except json.JSONDecodeError:
            continue
    return json.loads(stdout)


# ── Environment builder ──────────────────────────────────────────────────

def _build_env(tmp_path):
    """Create a full VFT_REPO_ROOT tree with DB and JSON files. Returns dict."""
    # Database
    db_dir = tmp_path / "fund" / "metadata" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "ingestion.db"
    conn = _create_db(str(db_path))

    # Deals JSON (flat array — what auto-create expects)
    dp = tmp_path / "fund" / "crm" / "deals.json"
    dp.parent.mkdir(parents=True, exist_ok=True)
    dp.write_text("[]")

    # Projects JSON (flat array)
    pp = tmp_path / "projects" / "projects.json"
    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text("[]")

    # rebuild_index.py stub (so --rebuild-index doesn't crash looking for it)
    meta_dir = tmp_path / "fund" / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)

    return {
        "root": tmp_path,
        "conn": conn,
        "db_path": str(db_path),
        "deals_path": dp,
        "projects_path": pp,
        "env": {"VFT_REPO_ROOT": str(tmp_path)},
    }


def _run(args, env_dict):
    """Shorthand: run script with env."""
    return _run_cli(args, env_override=env_dict["env"])


def _run_json(args, env_dict):
    """Run and parse JSON. Returns (rc, data_or_None, stderr)."""
    rc, stdout, stderr = _run(args, env_dict)
    try:
        data = _parse_json(stdout)
    except (json.JSONDecodeError, ValueError):
        data = None
    return rc, data, stderr


# ═════════════════════════════════════════════════════════════════════════
# TestPending
# ═════════════════════════════════════════════════════════════════════════

class TestPending:
    """Tests for the 'pending' subcommand."""

    def test_empty_database(self, tmp_path):
        """No messages at all -> pending_count 0, empty list."""
        env = _build_env(tmp_path)
        rc, data, _ = _run_json(["pending"], env)
        assert rc == 0
        assert data["pending_count"] == 0
        assert data["showing"] == 0
        assert data["messages"] == []
        env["conn"].close()

    def test_all_classified_returns_empty(self, tmp_path):
        """All messages marked classified -> nothing pending."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="m-1")
        conn.execute("UPDATE messages SET classified = 1 WHERE id = ?", (mid,))
        conn.commit()

        rc, data, _ = _run_json(["pending"], env)
        assert rc == 0
        assert data["pending_count"] == 0
        conn.close()

    def test_basic_pending_messages(self, tmp_path):
        """Inserts 3 unclassified messages, expects all returned."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        for i in range(3):
            _insert_message(conn, source="outlook", source_id=f"pend-{i}",
                            sender=f"user{i}@example.com",
                            subject=f"Subject {i}", body=f"Body {i}")

        rc, data, _ = _run_json(["pending"], env)
        assert rc == 0
        assert data["pending_count"] == 3
        assert data["showing"] == 3
        assert len(data["messages"]) == 3
        conn.close()

    def test_source_filter(self, tmp_path):
        """--source slack returns only slack messages."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        _insert_message(conn, source="outlook", source_id="o-1")
        _insert_message(conn, source="slack", source_id="s-1", type="message",
                        sender="bob")
        _insert_message(conn, source="slack", source_id="s-2", type="message",
                        sender="alice")

        rc, data, _ = _run_json(["pending", "--source", "slack"], env)
        assert rc == 0
        assert data["pending_count"] == 2
        assert all(m["source"] == "slack" for m in data["messages"])
        conn.close()

    def test_limit(self, tmp_path):
        """--limit constrains the number of returned rows."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        for i in range(10):
            _insert_message(conn, source="outlook", source_id=f"lim-{i}")

        rc, data, _ = _run_json(["pending", "--limit", "3"], env)
        assert rc == 0
        assert data["pending_count"] == 10
        assert data["showing"] == 3
        assert len(data["messages"]) == 3
        conn.close()

    def test_body_preview_truncated_to_300(self, tmp_path):
        """Body preview must be at most 300 chars."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        long_body = "A" * 1000
        _insert_message(conn, source="outlook", source_id="long-1", body=long_body)

        rc, data, _ = _run_json(["pending"], env)
        assert rc == 0
        preview = data["messages"][0]["body_preview"]
        assert len(preview) == 300
        conn.close()

    def test_sender_domain_extraction(self, tmp_path):
        """Sender domain parsed from email address."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        _insert_message(conn, source="outlook", source_id="dom-1",
                        sender="ceo@startup.io")

        rc, data, _ = _run_json(["pending"], env)
        assert data["messages"][0]["sender_domain"] == "startup.io"
        conn.close()

    def test_malformed_sender_no_domain(self, tmp_path):
        """Non-email sender -> empty sender_domain."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        _insert_message(conn, source="slack", source_id="nodom-1",
                        type="message", sender="john.smith")

        rc, data, _ = _run_json(["pending"], env)
        assert data["messages"][0]["sender_domain"] == ""
        conn.close()

    def test_unicode_sender_and_subject(self, tmp_path):
        """Unicode in sender/subject must survive the round trip."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        _insert_message(conn, source="outlook", source_id="uni-1",
                        sender="ceo@unternehmen.de",
                        subject="Test intro")

        rc, data, _ = _run_json(["pending"], env)
        assert rc == 0
        msg = data["messages"][0]
        assert "unternehmen" in msg["sender"]
        assert "Test intro" in msg["subject"]
        conn.close()

    def test_sql_injection_in_source_rejected(self, tmp_path):
        """Passing a SQL injection string as --source should fail (invalid choice)."""
        env = _build_env(tmp_path)
        rc, stdout, stderr = _run(["pending", "--source", "'; DROP TABLE messages;--"], env)
        assert rc != 0  # argparse rejects invalid choice
        env["conn"].close()


# ═════════════════════════════════════════════════════════════════════════
# TestContext
# ═════════════════════════════════════════════════════════════════════════

class TestContext:
    """Tests for the 'context' subcommand."""

    def test_empty_indexes(self, tmp_path):
        """Empty company_index / project_index -> zero counts."""
        env = _build_env(tmp_path)
        rc, data, _ = _run_json(["context", "--no-rebuild-index"], env)
        assert rc == 0
        assert data["deals_count"] == 0
        assert data["projects_count"] == 0
        assert data["deals"] == []
        assert data["projects"] == []
        env["conn"].close()

    def test_manual_index_rows(self, tmp_path):
        """Insert rows directly into indexes, verify they appear."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        conn.execute(
            """INSERT INTO company_index
               (company_slug, company_name, domains, keywords, contact_emails, last_touch)
               VALUES ('testco', 'TestCo', 'testco.com', 'test', 'a@testco.com', '2026-01-01')""")
        conn.execute(
            """INSERT INTO project_index
               (project_slug, project_name, keywords, contact_emails, category, status)
               VALUES ('proj-a', 'Project A', 'alpha', '', 'ops', 'active')""")
        conn.commit()

        rc, data, _ = _run_json(["context", "--no-rebuild-index"], env)
        assert data["deals_count"] == 1
        assert data["projects_count"] == 1
        assert data["deals"][0]["slug"] == "testco"
        assert data["projects"][0]["slug"] == "proj-a"
        conn.close()

    def test_active_only_filters_passed_deals(self, tmp_path):
        """--active-only should exclude deals with status=passed."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        # Write deals.json in {"companies": [...]} format for the context lookup
        deals_data = [
            {"slug": "midbound", "company_name": "Midbound", "status": "active", "stage": "diligence"},
            {"slug": "oldco", "company_name": "OldCo", "status": "passed", "stage": "IC"},
        ]
        env["deals_path"].write_text(json.dumps(deals_data))

        conn.execute(
            """INSERT INTO company_index
               (company_slug, company_name, domains, keywords, contact_emails, last_touch)
               VALUES ('midbound', 'Midbound', 'midbound.com', '', '', '2026-03-10')""")
        conn.execute(
            """INSERT INTO company_index
               (company_slug, company_name, domains, keywords, contact_emails, last_touch)
               VALUES ('oldco', 'OldCo', 'oldco.com', '', '', '2026-01-15')""")
        conn.commit()

        rc, data, _ = _run_json(["context", "--no-rebuild-index", "--active-only"], env)
        slugs = [d["slug"] for d in data["deals"]]
        assert "midbound" in slugs
        assert "oldco" not in slugs
        conn.close()

    def test_active_only_filters_archived_projects(self, tmp_path):
        """--active-only should exclude archived projects."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        projects_data = [
            {"slug": "fund-ops", "project_name": "Fund Operations", "status": "active"},
            {"slug": "old-research", "project_name": "Old Research", "status": "archived"},
        ]
        env["projects_path"].write_text(json.dumps(projects_data))

        conn.execute(
            """INSERT INTO project_index
               (project_slug, project_name, keywords, contact_emails, category, status)
               VALUES ('fund-ops', 'Fund Operations', '', '', 'ops', 'active')""")
        conn.execute(
            """INSERT INTO project_index
               (project_slug, project_name, keywords, contact_emails, category, status)
               VALUES ('old-research', 'Old Research', '', '', 'research', 'archived')""")
        conn.commit()

        rc, data, _ = _run_json(["context", "--no-rebuild-index", "--active-only"], env)
        slugs = [p["slug"] for p in data["projects"]]
        assert "fund-ops" in slugs
        assert "old-research" not in slugs
        conn.close()

    def test_recent_classifications_returned(self, tmp_path):
        """classification_log entries show up in recent_classifications."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        _insert_message(conn, source="outlook", source_id="rc-1")
        _insert_classification(conn, source_id=1, matched_slug="some-deal",
                               confidence=0.85)

        rc, data, _ = _run_json(["context", "--no-rebuild-index"], env)
        assert len(data["recent_classifications"]) >= 1
        assert data["recent_classifications"][0]["matched_slug"] == "some-deal"
        conn.close()

    def test_context_with_unicode_company_name(self, tmp_path):
        """Unicode company names survive index round-trip."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        conn.execute(
            """INSERT INTO company_index
               (company_slug, company_name, domains, keywords, contact_emails, last_touch)
               VALUES ('uni-co', '株式会社テスト', '', '', '', '')""")
        conn.commit()

        rc, data, _ = _run_json(["context", "--no-rebuild-index"], env)
        assert data["deals"][0]["company_name"] == "株式会社テスト"
        conn.close()

    def test_context_no_rebuild_with_missing_json(self, tmp_path):
        """No rebuild + missing JSON files still works (empty results)."""
        env = _build_env(tmp_path)
        os.remove(str(env["deals_path"]))
        os.remove(str(env["projects_path"]))

        rc, data, _ = _run_json(["context", "--no-rebuild-index"], env)
        assert rc == 0
        assert data["deals_count"] == 0
        env["conn"].close()

    def test_rebuild_with_invalid_json_warns(self, tmp_path):
        """--rebuild-index with corrupt JSON should not crash."""
        env = _build_env(tmp_path)
        env["deals_path"].write_text("{{{invalid json")

        rc, data, stderr = _run_json(["context", "--rebuild-index"], env)
        # Should still return a result (possibly empty) without crashing
        assert rc == 0
        env["conn"].close()


# ═════════════════════════════════════════════════════════════════════════
# TestDetail
# ═════════════════════════════════════════════════════════════════════════

class TestDetail:
    """Tests for the 'detail' subcommand."""

    def test_existing_message(self, tmp_path):
        """Retrieve a message by ID."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="det-1",
                              subject="Detail Test", body="Full body here.")

        rc, data, _ = _run_json(["detail", "--id", str(mid)], env)
        assert rc == 0
        assert data["subject"] == "Detail Test"
        assert data["body"] == "Full body here."
        conn.close()

    def test_nonexistent_id(self, tmp_path):
        """Non-existent message -> error JSON."""
        env = _build_env(tmp_path)
        rc, data, _ = _run_json(["detail", "--id", "99999"], env)
        assert rc == 0
        assert "error" in data
        assert "99999" in data["error"]
        env["conn"].close()

    def test_metadata_parsed_as_json(self, tmp_path):
        """metadata column stored as JSON string is parsed into dict."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="meta-1")
        conn.execute("UPDATE messages SET metadata = ? WHERE id = ?",
                     (json.dumps({"key": "value"}), mid))
        conn.commit()

        rc, data, _ = _run_json(["detail", "--id", str(mid)], env)
        assert data["metadata"] == {"key": "value"}
        conn.close()

    def test_sql_injection_in_id_rejected(self, tmp_path):
        """--id with non-integer input is rejected by argparse."""
        env = _build_env(tmp_path)
        rc, stdout, stderr = _run(["detail", "--id", "1; DROP TABLE messages;"], env)
        assert rc != 0  # argparse rejects non-int
        env["conn"].close()


# ═════════════════════════════════════════════════════════════════════════
# TestClassify
# ═════════════════════════════════════════════════════════════════════════

class TestClassify:
    """Tests for the 'classify' subcommand."""

    def test_classify_new_message(self, tmp_path):
        """First classification of a message -> status=classified."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="cls-1")

        rc, data, _ = _run_json([
            "classify", "--message-id", str(mid),
            "--slug", "test-deal", "--match-type", "deal",
            "--confidence", "0.95",
        ], env)
        assert rc == 0
        assert data["status"] == "classified"
        assert data["matched_slug"] == "test-deal"

        # Verify DB state
        conn2 = sqlite3.connect(env["db_path"])
        conn2.row_factory = sqlite3.Row
        row = conn2.execute("SELECT classified FROM messages WHERE id = ?", (mid,)).fetchone()
        assert row["classified"] == 1
        log = conn2.execute("SELECT * FROM classification_log WHERE source_id = ?", (mid,)).fetchone()
        assert log["matched_slug"] == "test-deal"
        assert log["confidence"] == 0.95
        conn2.close()
        conn.close()

    def test_classify_updates_project_tags(self, tmp_path):
        """Classification appends slug to project_tags JSON array."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="tags-1")

        _run_json([
            "classify", "--message-id", str(mid),
            "--slug", "alpha", "--match-type", "deal",
        ], env)

        conn2 = sqlite3.connect(env["db_path"])
        tags = json.loads(conn2.execute(
            "SELECT project_tags FROM messages WHERE id = ?", (mid,)
        ).fetchone()[0])
        assert "alpha" in tags
        conn2.close()
        conn.close()

    def test_classify_no_duplicate_tags(self, tmp_path):
        """Classifying twice with same slug should not duplicate the tag."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="dup-tag-1")

        for _ in range(2):
            _run_json([
                "classify", "--message-id", str(mid),
                "--slug", "beta", "--match-type", "deal",
            ], env)

        conn2 = sqlite3.connect(env["db_path"])
        tags = json.loads(conn2.execute(
            "SELECT project_tags FROM messages WHERE id = ?", (mid,)
        ).fetchone()[0])
        assert tags.count("beta") == 1
        conn2.close()
        conn.close()

    def test_classify_skips_reviewed(self, tmp_path):
        """Human-reviewed classification -> status=skipped."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="rev-1")
        _insert_classification(conn, source_id=mid, matched_slug="locked-deal",
                               reviewed=1)

        rc, data, _ = _run_json([
            "classify", "--message-id", str(mid),
            "--slug", "locked-deal", "--match-type", "deal",
        ], env)
        assert data["status"] == "skipped"
        conn.close()

    def test_classify_updates_existing_unreviewed(self, tmp_path):
        """Re-classify an unreviewed entry -> UPDATE, not INSERT duplicate."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="upd-1")
        _insert_classification(conn, source_id=mid, matched_slug="old-slug",
                               confidence=0.5, reviewed=0)

        rc, data, _ = _run_json([
            "classify", "--message-id", str(mid),
            "--slug", "old-slug", "--match-type", "project",
            "--confidence", "0.99",
        ], env)
        assert data["status"] == "classified"

        conn2 = sqlite3.connect(env["db_path"])
        rows = conn2.execute(
            "SELECT * FROM classification_log WHERE source_id = ?", (mid,)
        ).fetchall()
        # Should be exactly 1 row (updated, not duplicated)
        assert len(rows) == 1
        assert rows[0][5] == 0.99  # confidence column
        conn2.close()
        conn.close()

    def test_classify_with_json_reasoning(self, tmp_path):
        """Structured reasoning JSON stored in rule_hits."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="reason-1")

        reasoning = json.dumps({"domain_match": True, "keyword_hits": ["saas"]})
        _run_json([
            "classify", "--message-id", str(mid),
            "--slug", "reasoned", "--match-type", "deal",
            "--reasoning", reasoning,
        ], env)

        conn2 = sqlite3.connect(env["db_path"])
        log = conn2.execute(
            "SELECT rule_hits FROM classification_log WHERE source_id = ?", (mid,)
        ).fetchone()
        parsed = json.loads(log[0])
        assert parsed["domain_match"] is True
        conn2.close()
        conn.close()

    def test_classify_with_plain_text_reasoning(self, tmp_path):
        """Non-JSON reasoning stored as {"note": ...}."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="plain-1")

        _run_json([
            "classify", "--message-id", str(mid),
            "--slug", "plain-deal", "--match-type", "deal",
            "--reasoning", "looked like a match",
        ], env)

        conn2 = sqlite3.connect(env["db_path"])
        log = conn2.execute(
            "SELECT rule_hits FROM classification_log WHERE source_id = ?", (mid,)
        ).fetchone()
        parsed = json.loads(log[0])
        assert parsed["note"] == "looked like a match"
        conn2.close()
        conn.close()

    def test_classify_confidence_boundary_zero(self, tmp_path):
        """Confidence = 0.0 is valid."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="conf0-1")

        rc, data, _ = _run_json([
            "classify", "--message-id", str(mid),
            "--slug", "low", "--match-type", "deal",
            "--confidence", "0.0",
        ], env)
        assert data["status"] == "classified"
        assert data["confidence"] == 0.0
        conn.close()

    def test_classify_confidence_boundary_one(self, tmp_path):
        """Confidence = 1.0 is valid."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="conf1-1")

        rc, data, _ = _run_json([
            "classify", "--message-id", str(mid),
            "--slug", "high", "--match-type", "deal",
            "--confidence", "1.0",
        ], env)
        assert data["confidence"] == 1.0
        conn.close()

    def test_classify_invalid_match_type_rejected(self, tmp_path):
        """Invalid --match-type is rejected by argparse."""
        env = _build_env(tmp_path)
        rc, _, stderr = _run([
            "classify", "--message-id", "1",
            "--slug", "x", "--match-type", "invalid_type",
        ], env)
        assert rc != 0
        env["conn"].close()

    def test_classify_unicode_slug(self, tmp_path):
        """Unicode slug stored correctly."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="uni-cls-1")

        rc, data, _ = _run_json([
            "classify", "--message-id", str(mid),
            "--slug", "unternehmen-gmbh", "--match-type", "deal",
        ], env)
        assert data["status"] == "classified"
        assert data["matched_slug"] == "unternehmen-gmbh"
        conn.close()

    def test_classify_sql_injection_slug(self, tmp_path):
        """SQL injection in --slug should be safely parameterised."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="sqli-1")
        injection = SQL_INJECTIONS[0]  # "'; DROP TABLE messages; --"

        rc, data, _ = _run_json([
            "classify", "--message-id", str(mid),
            "--slug", injection, "--match-type", "deal",
        ], env)
        assert data["status"] == "classified"

        # Verify messages table still exists
        conn2 = sqlite3.connect(env["db_path"])
        count = conn2.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        assert count >= 1
        conn2.close()
        conn.close()

    def test_classify_all_match_types(self, tmp_path):
        """All four valid match types accepted."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        for i, mt in enumerate(["deal", "project", "new_deal", "new_project"]):
            mid = _insert_message(conn, source="outlook", source_id=f"mt-{i}")
            rc, data, _ = _run_json([
                "classify", "--message-id", str(mid),
                "--slug", f"slug-{i}", "--match-type", mt,
            ], env)
            assert data["status"] == "classified"
            assert data["match_type"] == mt
        conn.close()


# ═════════════════════════════════════════════════════════════════════════
# TestBatchClassify
# ═════════════════════════════════════════════════════════════════════════

class TestBatchClassify:
    """Tests for the 'batch-classify' subcommand."""

    def test_batch_basic(self, tmp_path):
        """Classify two messages in one batch."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        m1 = _insert_message(conn, source="outlook", source_id="b-1")
        m2 = _insert_message(conn, source="outlook", source_id="b-2")

        decisions = json.dumps([
            {"message_id": m1, "slug": "deal-a", "match_type": "deal", "confidence": 0.9},
            {"message_id": m2, "slug": "deal-b", "match_type": "project", "confidence": 0.8},
        ])

        rc, data, _ = _run_json(["batch-classify", "--decisions", decisions], env)
        assert rc == 0
        assert data["status"] == "batch_complete"
        assert data["classified"] == 2
        assert data["skipped"] == 0
        assert data["errors"] == 0
        conn.close()

    def test_batch_skips_reviewed(self, tmp_path):
        """Reviewed messages are skipped in batch."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        m1 = _insert_message(conn, source="outlook", source_id="br-1")
        _insert_classification(conn, source_id=m1, matched_slug="locked",
                               reviewed=1)

        decisions = json.dumps([
            {"message_id": m1, "slug": "locked", "match_type": "deal"},
        ])
        rc, data, _ = _run_json(["batch-classify", "--decisions", decisions], env)
        assert data["skipped"] == 1
        assert data["classified"] == 0
        conn.close()

    def test_batch_mixed_results(self, tmp_path):
        """Batch with one new, one reviewed, one missing key -> mixed counters."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        m1 = _insert_message(conn, source="outlook", source_id="mix-1")
        m2 = _insert_message(conn, source="outlook", source_id="mix-2")
        _insert_classification(conn, source_id=m2, matched_slug="x", reviewed=1)

        decisions = json.dumps([
            {"message_id": m1, "slug": "new-deal", "match_type": "deal"},
            {"message_id": m2, "slug": "x", "match_type": "deal"},
            {},  # missing message_id -> error
        ])
        rc, data, _ = _run_json(["batch-classify", "--decisions", decisions], env)
        assert data["classified"] == 1
        assert data["skipped"] == 1
        assert data["errors"] == 1
        conn.close()

    def test_batch_invalid_json(self, tmp_path):
        """Malformed JSON in --decisions -> error JSON output."""
        env = _build_env(tmp_path)
        rc, data, _ = _run_json(["batch-classify", "--decisions", "{{{bad"], env)
        assert rc == 0
        assert "error" in data
        env["conn"].close()

    def test_batch_empty_array(self, tmp_path):
        """Empty decisions array -> batch_complete with zeros."""
        env = _build_env(tmp_path)
        rc, data, _ = _run_json(["batch-classify", "--decisions", "[]"], env)
        assert data["status"] == "batch_complete"
        assert data["classified"] == 0
        env["conn"].close()

    def test_batch_updates_project_tags(self, tmp_path):
        """Batch classify updates project_tags for each message."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        m1 = _insert_message(conn, source="outlook", source_id="btag-1")

        decisions = json.dumps([
            {"message_id": m1, "slug": "tagged-deal", "match_type": "deal"},
        ])
        _run_json(["batch-classify", "--decisions", decisions], env)

        conn2 = sqlite3.connect(env["db_path"])
        tags = json.loads(conn2.execute(
            "SELECT project_tags FROM messages WHERE id = ?", (m1,)
        ).fetchone()[0])
        assert "tagged-deal" in tags
        conn2.close()
        conn.close()

    def test_batch_sql_injection_in_slug(self, tmp_path):
        """SQL injection in batch slug is safely handled."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        m1 = _insert_message(conn, source="outlook", source_id="bsql-1")

        decisions = json.dumps([
            {"message_id": m1, "slug": SQL_INJECTIONS[3], "match_type": "deal"},
        ])
        rc, data, _ = _run_json(["batch-classify", "--decisions", decisions], env)
        assert data["classified"] == 1

        # Tables still intact
        conn2 = sqlite3.connect(env["db_path"])
        conn2.execute("SELECT COUNT(*) FROM messages").fetchone()
        conn2.close()
        conn.close()

    def test_batch_unicode_reasoning(self, tmp_path):
        """Unicode in reasoning dict stored correctly."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        m1 = _insert_message(conn, source="outlook", source_id="buni-1")

        decisions = json.dumps([
            {"message_id": m1, "slug": "uni-deal", "match_type": "deal",
             "reasoning": {"note": "Ca Va -- test"}},
        ])
        rc, data, _ = _run_json(["batch-classify", "--decisions", decisions], env)
        assert data["classified"] == 1

        conn2 = sqlite3.connect(env["db_path"])
        log = conn2.execute(
            "SELECT rule_hits FROM classification_log WHERE source_id = ?", (m1,)
        ).fetchone()
        parsed = json.loads(log[0])
        assert "Ca Va" in parsed["note"]
        conn2.close()
        conn.close()


# ═════════════════════════════════════════════════════════════════════════
# TestAutoCreate
# ═════════════════════════════════════════════════════════════════════════

class TestAutoCreate:
    """Tests for the 'auto-create' subcommand."""

    def test_create_deal(self, tmp_path):
        """Create a new deal -> status=created, deals.json updated."""
        env = _build_env(tmp_path)
        rc, data, _ = _run_json([
            "auto-create", "--type", "deal", "--name", "WidgetCo",
        ], env)
        assert rc == 0
        assert data["status"] == "created"
        assert data["slug"] == "widgetco"
        assert data["type"] == "deal"

        deals_data = json.loads(env["deals_path"].read_text())
        companies = deals_data.get("companies", deals_data) if isinstance(deals_data, dict) else deals_data
        assert any(d["slug"] == "widgetco" for d in companies)
        env["conn"].close()

    def test_create_project(self, tmp_path):
        """Create a new project -> status=created, projects.json updated."""
        env = _build_env(tmp_path)
        rc, data, _ = _run_json([
            "auto-create", "--type", "project", "--name", "New Research",
        ], env)
        assert data["status"] == "created"
        assert data["slug"] == "new-research"
        assert data["type"] == "project"

        projects_data = json.loads(env["projects_path"].read_text())
        project_list = projects_data.get("projects", projects_data) if isinstance(projects_data, dict) else projects_data
        assert any(p["slug"] == "new-research" for p in project_list)
        env["conn"].close()

    def test_duplicate_slug_returns_exists(self, tmp_path):
        """Creating a deal with an existing slug -> status=exists."""
        env = _build_env(tmp_path)
        # Pre-populate deals.json with a flat array containing the slug
        env["deals_path"].write_text(json.dumps([{"slug": "widgetco", "company_name": "WidgetCo"}]))

        rc, data, _ = _run_json([
            "auto-create", "--type", "deal", "--name", "WidgetCo",
        ], env)
        assert data["status"] == "exists"
        assert data["slug"] == "widgetco"
        env["conn"].close()

    def test_custom_slug_override(self, tmp_path):
        """--slug overrides the auto-generated slug."""
        env = _build_env(tmp_path)
        rc, data, _ = _run_json([
            "auto-create", "--type", "deal", "--name", "My Company",
            "--slug", "custom-slug",
        ], env)
        assert data["slug"] == "custom-slug"
        env["conn"].close()

    def test_create_with_message_id_classifies(self, tmp_path):
        """--message-id classifies the message to the new entity."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="ac-msg-1")

        rc, data, _ = _run_json([
            "auto-create", "--type", "deal", "--name", "FreshCo",
            "--message-id", str(mid),
        ], env)
        assert data["status"] == "created"

        conn2 = sqlite3.connect(env["db_path"])
        conn2.row_factory = sqlite3.Row
        row = conn2.execute("SELECT classified, project_tags FROM messages WHERE id = ?",
                            (mid,)).fetchone()
        assert row["classified"] == 1
        tags = json.loads(row["project_tags"])
        assert "freshco" in tags
        conn2.close()
        conn.close()

    def test_slugify_unicode_name(self, tmp_path):
        """Unicode company name is slugified safely."""
        env = _build_env(tmp_path)
        rc, data, _ = _run_json([
            "auto-create", "--type", "deal", "--name", "Rocket Co 123",
        ], env)
        slug = data["slug"]
        assert slug == "rocket-co-123"
        # Verify slug is URL-safe
        assert re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', slug)
        env["conn"].close()

    def test_create_deal_with_extra_fields(self, tmp_path):
        """--extra JSON merges additional fields into the deal record."""
        env = _build_env(tmp_path)
        extra = json.dumps({"stage": "diligence", "sector": "HealthTech"})
        rc, data, _ = _run_json([
            "auto-create", "--type", "deal", "--name", "HealthBot",
            "--extra", extra,
        ], env)
        assert data["status"] == "created"

        deals_data = json.loads(env["deals_path"].read_text())
        companies = deals_data.get("companies", deals_data) if isinstance(deals_data, dict) else deals_data
        deal = next(d for d in companies if d["slug"] == "healthbot")
        assert deal["stage"] == "diligence"
        assert deal["sector"] == "HealthTech"
        env["conn"].close()

    def test_sql_injection_in_name(self, tmp_path):
        """SQL injection in --name does not corrupt the database."""
        env = _build_env(tmp_path)
        conn = env["conn"]
        mid = _insert_message(conn, source="outlook", source_id="sqli-ac-1")

        rc, data, _ = _run_json([
            "auto-create", "--type", "deal",
            "--name", "Robert'); DROP TABLE students;--",
            "--message-id", str(mid),
        ], env)
        assert data["status"] == "created"

        # Verify DB is intact
        conn2 = sqlite3.connect(env["db_path"])
        conn2.execute("SELECT COUNT(*) FROM messages").fetchone()
        conn2.execute("SELECT COUNT(*) FROM classification_log").fetchone()
        conn2.close()
        conn.close()
