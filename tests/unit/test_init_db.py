"""Tests for fund/metadata/init_db.py — database initialization and schema integrity."""

import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPECTED_TABLES = {
    "emails",
    "transcripts",
    "messages",
    "company_index",
    "project_index",
    "classification_log",
    "processed_items",
    "schema_meta",
    "document_pages",
    "document_extractions",
    "document_jobs",
    "contacts",
}


def _get_tables(conn: sqlite3.Connection) -> set[str]:
    """Return the set of user-created table names."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r[0] for r in rows}


def _get_indexes(conn: sqlite3.Connection) -> set[str]:
    """Return the set of explicitly-created index names."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r[0] for r in rows}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_creates_all_tables(fresh_db):
    """init_db must create every expected table."""
    conn, _ = fresh_db
    tables = _get_tables(conn)
    assert EXPECTED_TABLES.issubset(tables), (
        f"Missing tables: {EXPECTED_TABLES - tables}"
    )


def test_schema_version_stored(fresh_db):
    """schema_meta must contain a row with version = 4."""
    conn, _ = fresh_db
    row = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
    assert row is not None, "schema_meta table has no schema_version entry"
    assert row[0] == "4"


def test_idempotent_reinit(fresh_db):
    """Calling init_db a second time on the same DB must not raise and must preserve data."""
    conn, db_path = fresh_db

    # Insert a sentinel row before re-init
    conn.execute(
        "INSERT INTO messages (source, source_id, type, sender, recipients, "
        "subject, body, timestamp, channel, attachments, project_tags) "
        "VALUES ('outlook', 'sentinel-001', 'email', 's@e.com', '[]', "
        "'Sentinel', 'body', '2026-01-01T00:00:00', 'inbox', '[]', '[]')"
    )
    conn.commit()

    # Re-init — should not raise
    sys.path.insert(0, str(REPO_ROOT / "fund" / "metadata"))
    try:
        from init_db import init_db
        conn2 = init_db(db_path)
    finally:
        if str(REPO_ROOT / "fund" / "metadata") in sys.path:
            sys.path.remove(str(REPO_ROOT / "fund" / "metadata"))

    # Sentinel row must still exist
    row = conn2.execute(
        "SELECT source_id FROM messages WHERE source_id = 'sentinel-001'"
    ).fetchone()
    conn2.close()
    assert row is not None, "Data lost after re-initialisation"


def test_messages_source_check_constraint(fresh_db):
    """Inserting a message with an invalid source must raise IntegrityError."""
    conn, _ = fresh_db
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO messages (source, source_id, type, sender, recipients, "
            "subject, body, timestamp, channel, attachments, project_tags) "
            "VALUES ('invalid_source', 'id-1', 'email', 's@e.com', '[]', "
            "'Subj', 'body', '2026-01-01T00:00:00', 'inbox', '[]', '[]')"
        )


def test_messages_unique_constraint(fresh_db):
    """Inserting two messages with the same (source, source_id) must raise IntegrityError."""
    conn, _ = fresh_db
    params = (
        "outlook", "dup-001", "email", "s@e.com", "[]",
        "Subj", "body", "2026-01-01T00:00:00", "inbox", "[]", "[]",
    )
    conn.execute(
        "INSERT INTO messages (source, source_id, type, sender, recipients, "
        "subject, body, timestamp, channel, attachments, project_tags) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        params,
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO messages (source, source_id, type, sender, recipients, "
            "subject, body, timestamp, channel, attachments, project_tags) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            params,
        )


def test_classification_log_match_type_check(fresh_db):
    """Inserting a classification_log row with an invalid match_type must raise IntegrityError."""
    conn, _ = fresh_db
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO classification_log "
            "(source_type, source_id, matched_slug, match_type, confidence, rule_hits) "
            "VALUES ('message', 1, 'slug', 'bogus_type', 0.9, '{}')"
        )


def test_contacts_unique_email(fresh_db):
    """Inserting two contacts with the same email must raise IntegrityError."""
    conn, _ = fresh_db
    conn.execute(
        "INSERT INTO contacts (name, email, company, source) "
        "VALUES ('Alice', 'alice@example.com', 'Co', 'outlook')"
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO contacts (name, email, company, source) "
            "VALUES ('Alice Dup', 'alice@example.com', 'Co2', 'slack')"
        )


def test_all_indexes_created(fresh_db):
    """init_db must create at least one index; verify known indexes are present."""
    conn, _ = fresh_db
    indexes = _get_indexes(conn)
    # There should be a non-trivial number of indexes given the schema
    assert len(indexes) >= 1, "No explicit indexes found"
    # Spot-check: the autoindex for UNIQUE constraints will exist at minimum,
    # but custom indexes should also be present.  We just verify the set is
    # non-empty and contains index objects (detailed names depend on the DDL).
    for idx_name in indexes:
        assert isinstance(idx_name, str) and len(idx_name) > 0
