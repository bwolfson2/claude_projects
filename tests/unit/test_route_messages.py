"""Tests for skills/reactive-router/scripts/route_messages.py — routing CLI."""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Resolve to the real repo root (worktree may be sparse), so we can
# find the script under skills/ and the schema under fund/metadata/.
REPO_ROOT = Path(os.environ.get(
    "VFT_REPO_ROOT",
    Path(__file__).resolve().parents[2],
))
# Walk up from the test file to find the actual repo root that has the script
_test_root = Path(__file__).resolve().parents[2]
# The script lives in the main repo, not in the worktree
_MAIN_REPO = Path(__file__).resolve()
for _p in _MAIN_REPO.parents:
    if (_p / "skills" / "reactive-router" / "scripts" / "route_messages.py").exists():
        _MAIN_REPO = _p
        break

SCRIPT = _MAIN_REPO / "skills" / "reactive-router" / "scripts" / "route_messages.py"
INIT_DB = _MAIN_REPO / "fund" / "metadata" / "init_db.py"

# Import init_db for schema creation
sys.path.insert(0, str(INIT_DB.parent))
from init_db import init_db

SQL_INJECTIONS = [
    "'; DROP TABLE messages; --",
    '" OR 1=1 --',
    "<script>alert(1)</script>",
    "Robert'); DROP TABLE students;--",
    "1; UPDATE messages SET classified=1 WHERE 1=1;--",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path):
    """Create a DB at the expected location under tmp_path. Returns (conn, db_path)."""
    db_dir = tmp_path / "fund" / "metadata" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "ingestion.db"
    conn = init_db(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn, db_path


def _env(tmp_path):
    """Return env dict pointing VFT_REPO_ROOT at tmp_path."""
    env = os.environ.copy()
    env["VFT_REPO_ROOT"] = str(tmp_path)
    return env


def _run(args, env):
    """Run route_messages.py as a subprocess."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def _parse(stdout):
    """Parse JSON from stdout, searching for the first valid JSON block."""
    lines = stdout.strip().split("\n")
    for i in range(len(lines)):
        try:
            return json.loads("\n".join(lines[i:]))
        except json.JSONDecodeError:
            continue
    return json.loads(stdout)


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
    """Insert a classification_log entry. Returns the new row id."""
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


@pytest.fixture
def route_env(tmp_path):
    """Provide a tmp_path with a DB at the right location, env dict, and connection."""
    conn, db_path = _make_db(tmp_path)
    env = _env(tmp_path)
    yield conn, db_path, env, tmp_path
    conn.close()


# ===========================================================================
# TestPending
# ===========================================================================


class TestPending:
    """Tests for the 'pending' subcommand."""

    def test_empty_db_returns_zero(self, route_env):
        """An empty DB should return pending_count=0 and no messages."""
        conn, db_path, env, tmp = route_env
        rc, stdout, stderr = _run(["pending"], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["pending_count"] == 0
        assert data["showing"] == 0
        assert data["messages"] == []

    def test_returns_classified_unrouted_messages(self, route_env):
        """Only classified=1 AND routed_at IS NULL should appear."""
        conn, db_path, env, tmp = route_env
        m1 = _insert_message(conn, source_id="pend-1")
        m2 = _insert_message(conn, source_id="pend-2")
        m3 = _insert_message(conn, source_id="pend-3")
        # Classify m1 and m2, leave m3 unclassified
        conn.execute("UPDATE messages SET classified = 1 WHERE id IN (?, ?)", (m1, m2))
        # Route m1 so it's excluded
        conn.execute("UPDATE messages SET routed_at = ? WHERE id = ?",
                     (datetime.now().isoformat(), m1))
        conn.commit()

        rc, stdout, _ = _run(["pending"], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["pending_count"] == 1
        ids = [m["id"] for m in data["messages"]]
        assert m2 in ids
        assert m1 not in ids
        assert m3 not in ids

    def test_limit_parameter(self, route_env):
        """--limit should restrict the number of returned messages."""
        conn, db_path, env, tmp = route_env
        for i in range(5):
            mid = _insert_message(conn, source_id=f"lim-{i}")
            conn.execute("UPDATE messages SET classified = 1 WHERE id = ?", (mid,))
        conn.commit()

        rc, stdout, _ = _run(["pending", "--limit", "2"], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["showing"] == 2
        # pending_count reflects total, not limited
        assert data["pending_count"] == 5

    def test_project_filter(self, route_env):
        """--project should filter by project_tags or matched_slug."""
        conn, db_path, env, tmp = route_env
        m1 = _insert_message(conn, source_id="proj-1",
                             project_tags='["alpha"]')
        m2 = _insert_message(conn, source_id="proj-2",
                             project_tags='["beta"]')
        conn.execute("UPDATE messages SET classified = 1 WHERE id IN (?, ?)", (m1, m2))
        conn.commit()

        rc, stdout, _ = _run(["pending", "--project", "alpha"], env)
        assert rc == 0
        data = _parse(stdout)
        ids = [m["id"] for m in data["messages"]]
        assert m1 in ids
        assert m2 not in ids

    def test_body_preview_truncation(self, route_env):
        """Body should be truncated to 300 chars in body_preview."""
        conn, db_path, env, tmp = route_env
        long_body = "A" * 500
        mid = _insert_message(conn, source_id="trunc-1", body=long_body)
        conn.execute("UPDATE messages SET classified = 1 WHERE id = ?", (mid,))
        conn.commit()

        rc, stdout, _ = _run(["pending"], env)
        assert rc == 0
        data = _parse(stdout)
        assert len(data["messages"][0]["body_preview"]) == 300

    def test_sql_injection_in_project_filter(self, route_env):
        """SQL injection attempts in --project should not crash or corrupt."""
        conn, db_path, env, tmp = route_env
        mid = _insert_message(conn, source_id="sqlinj-1")
        conn.execute("UPDATE messages SET classified = 1 WHERE id = ?", (mid,))
        conn.commit()

        for payload in SQL_INJECTIONS:
            rc, stdout, _ = _run(["pending", "--project", payload], env)
            assert rc == 0
            data = _parse(stdout)
            assert "messages" in data

    def test_classification_join_returns_context(self, route_env):
        """Pending messages should include classification_log context when available.

        This test exposes the broken JOIN: m.source = cl.source_type will not
        match because messages.source contains 'outlook', 'slack', etc. while
        classification_log.source_type is always 'message'.
        """
        conn, db_path, env, tmp = route_env
        mid = _insert_message(conn, source="outlook", source_id="join-1")
        conn.execute("UPDATE messages SET classified = 1 WHERE id = ?", (mid,))
        # Insert classification with source_type='message' (the normal value
        # used by the classifier — never 'outlook')
        _insert_classification(conn, source_type="message", source_id=mid,
                               matched_slug="acme", confidence=0.95)
        conn.commit()

        rc, stdout, _ = _run(["pending"], env)
        assert rc == 0
        data = _parse(stdout)
        assert len(data["messages"]) == 1
        msg = data["messages"][0]
        # The bug: these will be empty/null because the JOIN doesn't match
        assert msg["matched_slug"] == "acme"
        assert msg["classification_confidence"] == 0.95


# ===========================================================================
# TestRoutes
# ===========================================================================


class TestRoutes:
    """Tests for the 'routes' subcommand."""

    def test_returns_all_route_definitions(self, route_env):
        """Should return all 7 route definitions."""
        conn, db_path, env, tmp = route_env
        rc, stdout, _ = _run(["routes"], env)
        assert rc == 0
        data = _parse(stdout)
        assert len(data["routes"]) == 7
        route_names = {r["route"] for r in data["routes"]}
        assert route_names == {
            "term_sheet", "dataroom", "meeting", "intro",
            "funding", "action_items", "follow_up",
        }

    def test_route_definitions_have_required_fields(self, route_env):
        """Every route must have route, priority, description, and typical_actions."""
        conn, db_path, env, tmp = route_env
        rc, stdout, _ = _run(["routes"], env)
        assert rc == 0
        data = _parse(stdout)
        for route in data["routes"]:
            assert "route" in route
            assert "priority" in route
            assert route["priority"] in ("URGENT", "HIGH", "MEDIUM", "LOW")
            assert "description" in route
            assert "typical_actions" in route
            assert isinstance(route["typical_actions"], list)


# ===========================================================================
# TestRoute
# ===========================================================================


class TestRoute:
    """Tests for the 'route' subcommand."""

    def test_route_single_message(self, route_env):
        """Basic routing should set routed_at and return JSON with all fields."""
        conn, db_path, env, tmp = route_env
        mid = _insert_message(conn, source_id="route-1")

        rc, stdout, _ = _run([
            "route", "--message-id", str(mid),
            "--route", "dataroom", "--priority", "HIGH",
            "--actions", '["download_attachments", "run_dataroom_intake"]',
        ], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["status"] == "routed"
        assert data["message_id"] == mid
        assert data["route"] == "dataroom"
        assert data["priority"] == "HIGH"
        assert data["actions"] == ["download_attachments", "run_dataroom_intake"]
        assert "reasoning" not in data

        # Verify DB was updated
        row = conn.execute("SELECT routed_at FROM messages WHERE id = ?", (mid,)).fetchone()
        assert row["routed_at"] is not None

    def test_route_with_reasoning(self, route_env):
        """--reasoning should appear in the output."""
        conn, db_path, env, tmp = route_env
        mid = _insert_message(conn, source_id="route-reason")

        rc, stdout, _ = _run([
            "route", "--message-id", str(mid),
            "--route", "term_sheet", "--priority", "URGENT",
            "--actions", '["flag_urgent"]',
            "--reasoning", "Sender attached term_sheet.pdf",
        ], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["reasoning"] == "Sender attached term_sheet.pdf"

    def test_route_actions_json_fallback(self, route_env):
        """Non-JSON --actions string should be wrapped in a list."""
        conn, db_path, env, tmp = route_env
        mid = _insert_message(conn, source_id="route-fallback")

        rc, stdout, _ = _run([
            "route", "--message-id", str(mid),
            "--route", "meeting", "--priority", "MEDIUM",
            "--actions", "create_meeting_prep",
        ], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["actions"] == ["create_meeting_prep"]

    def test_route_invalid_route_choice(self, route_env):
        """An invalid --route value should be rejected by argparse."""
        conn, db_path, env, tmp = route_env
        mid = _insert_message(conn, source_id="route-bad")

        rc, stdout, stderr = _run([
            "route", "--message-id", str(mid),
            "--route", "nonexistent", "--priority", "HIGH",
            "--actions", "[]",
        ], env)
        assert rc != 0
        assert "invalid choice" in stderr.lower()

    def test_route_invalid_priority_choice(self, route_env):
        """An invalid --priority value should be rejected by argparse."""
        conn, db_path, env, tmp = route_env
        mid = _insert_message(conn, source_id="route-badpri")

        rc, stdout, stderr = _run([
            "route", "--message-id", str(mid),
            "--route", "meeting", "--priority", "CRITICAL",
            "--actions", "[]",
        ], env)
        assert rc != 0
        assert "invalid choice" in stderr.lower()

    def test_route_nonexistent_message(self, route_env):
        """Routing a message ID that doesn't exist should still succeed (UPDATE affects 0 rows)."""
        conn, db_path, env, tmp = route_env

        rc, stdout, _ = _run([
            "route", "--message-id", "99999",
            "--route", "follow_up", "--priority", "LOW",
            "--actions", '["update_last_touch"]',
        ], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["status"] == "routed"
        assert data["message_id"] == 99999

    def test_route_already_routed_message(self, route_env):
        """Routing an already-routed message should overwrite routed_at."""
        conn, db_path, env, tmp = route_env
        mid = _insert_message(conn, source_id="route-dup")
        conn.execute("UPDATE messages SET routed_at = '2020-01-01T00:00:00' WHERE id = ?", (mid,))
        conn.commit()

        rc, stdout, _ = _run([
            "route", "--message-id", str(mid),
            "--route", "intro", "--priority", "MEDIUM",
            "--actions", '["create_deal"]',
        ], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["status"] == "routed"

        row = conn.execute("SELECT routed_at FROM messages WHERE id = ?", (mid,)).fetchone()
        assert row["routed_at"] != "2020-01-01T00:00:00"


# ===========================================================================
# TestBatchRoute
# ===========================================================================


class TestBatchRoute:
    """Tests for the 'batch-route' subcommand."""

    def test_batch_route_multiple(self, route_env):
        """Batch route several messages at once."""
        conn, db_path, env, tmp = route_env
        m1 = _insert_message(conn, source_id="batch-1")
        m2 = _insert_message(conn, source_id="batch-2")

        decisions = json.dumps([
            {"message_id": m1, "route": "dataroom", "priority": "HIGH",
             "actions": ["download_attachments"]},
            {"message_id": m2, "route": "meeting", "priority": "MEDIUM",
             "actions": ["create_meeting_prep"]},
        ])

        rc, stdout, _ = _run(["batch-route", "--decisions", decisions], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["status"] == "batch_complete"
        assert data["routed"] == 2
        assert len(data["action_plan"]) == 2

        # Verify DB
        for mid in (m1, m2):
            row = conn.execute("SELECT routed_at FROM messages WHERE id = ?", (mid,)).fetchone()
            assert row["routed_at"] is not None

    def test_batch_route_invalid_json(self, route_env):
        """Invalid JSON in --decisions should return an error, not crash."""
        conn, db_path, env, tmp = route_env

        rc, stdout, _ = _run(["batch-route", "--decisions", "not-json{["], env)
        assert rc == 0  # Script handles gracefully
        data = _parse(stdout)
        assert "error" in data

    def test_batch_route_empty_array(self, route_env):
        """An empty decisions array should route 0 messages."""
        conn, db_path, env, tmp = route_env

        rc, stdout, _ = _run(["batch-route", "--decisions", "[]"], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["status"] == "batch_complete"
        assert data["routed"] == 0
        assert data["action_plan"] == []

    def test_batch_route_actions_string_fallback(self, route_env):
        """Actions passed as a plain string should be wrapped in a list."""
        conn, db_path, env, tmp = route_env
        mid = _insert_message(conn, source_id="batch-str")

        decisions = json.dumps([
            {"message_id": mid, "route": "follow_up", "actions": "update_last_touch"},
        ])

        rc, stdout, _ = _run(["batch-route", "--decisions", decisions], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["action_plan"][0]["actions"] == ["update_last_touch"]

    def test_batch_route_actions_json_string(self, route_env):
        """Actions passed as a JSON-encoded string should be parsed."""
        conn, db_path, env, tmp = route_env
        mid = _insert_message(conn, source_id="batch-jstr")

        decisions = json.dumps([
            {"message_id": mid, "route": "dataroom",
             "actions": '["download_attachments", "run_dataroom_intake"]'},
        ])

        rc, stdout, _ = _run(["batch-route", "--decisions", decisions], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["action_plan"][0]["actions"] == ["download_attachments", "run_dataroom_intake"]

    def test_batch_route_missing_message_id_key(self, route_env):
        """A decision missing 'message_id' should be handled gracefully."""
        conn, db_path, env, tmp = route_env

        decisions = json.dumps([
            {"route": "meeting", "priority": "MEDIUM", "actions": []},
        ])

        rc, stdout, stderr = _run(["batch-route", "--decisions", decisions], env)
        # The script catches the KeyError and prints a warning to stderr
        assert rc == 0
        assert "warning" in stderr.lower() or "error" in stderr.lower()


# ===========================================================================
# TestMarkRouted
# ===========================================================================


class TestMarkRouted:
    """Tests for the 'mark-routed' subcommand."""

    def test_mark_single(self, route_env):
        """Mark a single message as routed."""
        conn, db_path, env, tmp = route_env
        mid = _insert_message(conn, source_id="mark-1")

        rc, stdout, _ = _run(["mark-routed", "--message-ids", str(mid)], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["status"] == "marked_routed"
        assert data["count"] == 1
        assert data["message_ids"] == [mid]

        row = conn.execute("SELECT routed_at FROM messages WHERE id = ?", (mid,)).fetchone()
        assert row["routed_at"] is not None

    def test_mark_multiple(self, route_env):
        """Mark several messages as routed with comma-separated IDs."""
        conn, db_path, env, tmp = route_env
        m1 = _insert_message(conn, source_id="mark-m1")
        m2 = _insert_message(conn, source_id="mark-m2")
        m3 = _insert_message(conn, source_id="mark-m3")

        rc, stdout, _ = _run(["mark-routed", "--message-ids", f"{m1},{m2},{m3}"], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["count"] == 3
        assert set(data["message_ids"]) == {m1, m2, m3}

    def test_mark_with_spaces(self, route_env):
        """IDs with spaces around commas should be handled by strip()."""
        conn, db_path, env, tmp = route_env
        m1 = _insert_message(conn, source_id="mark-sp1")
        m2 = _insert_message(conn, source_id="mark-sp2")

        rc, stdout, _ = _run(["mark-routed", "--message-ids", f" {m1} , {m2} "], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["count"] == 2

    def test_mark_nonexistent_ids(self, route_env):
        """Marking IDs that don't exist should succeed (UPDATE affects 0 rows)."""
        conn, db_path, env, tmp = route_env

        rc, stdout, _ = _run(["mark-routed", "--message-ids", "99998,99999"], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["count"] == 2
        assert data["message_ids"] == [99998, 99999]

    def test_mark_malformed_ids(self, route_env):
        """Non-integer IDs should cause a ValueError and nonzero exit."""
        conn, db_path, env, tmp = route_env

        rc, stdout, stderr = _run(["mark-routed", "--message-ids", "abc,def"], env)
        assert rc != 0  # int() conversion fails with unhandled ValueError

    def test_mark_already_routed(self, route_env):
        """Re-marking an already-routed message should overwrite routed_at."""
        conn, db_path, env, tmp = route_env
        mid = _insert_message(conn, source_id="mark-dup")
        conn.execute("UPDATE messages SET routed_at = '2020-01-01T00:00:00' WHERE id = ?", (mid,))
        conn.commit()

        rc, stdout, _ = _run(["mark-routed", "--message-ids", str(mid)], env)
        assert rc == 0
        data = _parse(stdout)
        assert data["count"] == 1

        row = conn.execute("SELECT routed_at FROM messages WHERE id = ?", (mid,)).fetchone()
        assert row["routed_at"] != "2020-01-01T00:00:00"


# ===========================================================================
# TestMissingDb — cross-cutting
# ===========================================================================


class TestMissingDb:
    """Test that the CLI exits with code 1 when DB_PATH doesn't exist."""

    def test_exits_when_db_missing(self, tmp_path):
        """All subcommands should fail if the database file is absent."""
        env = _env(tmp_path)
        # Don't create the DB directory at all

        for subcmd in ["pending", "routes"]:
            rc, stdout, stderr = _run([subcmd], env)
            assert rc == 1, f"Expected exit 1 for '{subcmd}', got {rc}. stderr: {stderr}"
            data = _parse(stdout)
            assert "error" in data
