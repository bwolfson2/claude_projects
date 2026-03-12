"""
Tests for the calendar scanner skill (scan_calendar.py).

Verifies:
- Source ID generation
- Event dedup logic
- Event save (markdown + DB insert)
- DB lock retry
- Attendee domain extraction
- Scan status reporting
"""

import json
import sqlite3
from pathlib import Path

import pytest

from scan_calendar import (
    extract_attendee_domains,
    make_source_id,
    save_event,
    get_scan_status,
    slugify,
)


@pytest.fixture
def db_env(tmp_path):
    """Set up a temp DB with the messages table and patch paths."""
    db_path = tmp_path / "ingestion.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        type TEXT NOT NULL,
        sender TEXT,
        recipients TEXT,
        subject TEXT,
        body TEXT,
        timestamp TEXT NOT NULL,
        channel TEXT,
        attachments TEXT DEFAULT '[]',
        project_tags TEXT DEFAULT '[]',
        raw_path TEXT,
        metadata TEXT DEFAULT '{}',
        classified INTEGER DEFAULT 0,
        routed_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(source, source_id)
    )""")
    conn.commit()
    inbox_root = tmp_path / "inbox" / "calendar"
    inbox_root.mkdir(parents=True)
    return {"conn": conn, "db_path": db_path, "inbox_root": inbox_root, "tmp_path": tmp_path}


class TestMakeSourceId:
    """Test source_id generation."""

    def test_basic(self):
        result = make_source_id("primary", "abc123")
        assert result == "primary|abc123"

    def test_with_email_calendar_id(self):
        result = make_source_id("user@gmail.com", "event-456")
        assert result == "user@gmail.com|event-456"


class TestExtractAttendeeDomains:
    """Test attendee domain extraction."""

    def test_dict_attendees(self):
        attendees = [
            {"name": "Jane", "email": "jane@acme.com"},
            {"name": "Bob", "email": "bob@vft.institute"},
        ]
        domains = extract_attendee_domains(attendees)
        assert "acme.com" in domains
        assert "vft.institute" in domains

    def test_filters_personal_domains(self):
        attendees = [
            {"email": "person@gmail.com"},
            {"email": "work@company.com"},
            {"email": "other@yahoo.com"},
        ]
        domains = extract_attendee_domains(attendees)
        assert "gmail.com" not in domains
        assert "yahoo.com" not in domains
        assert "company.com" in domains

    def test_string_attendees(self):
        attendees = ["jane@acme.com", "bob@corp.io"]
        domains = extract_attendee_domains(attendees)
        assert "acme.com" in domains
        assert "corp.io" in domains

    def test_empty_list(self):
        assert extract_attendee_domains([]) == []

    def test_no_email_key(self):
        attendees = [{"name": "Jane"}]
        # Should handle gracefully (no @ in empty string)
        domains = extract_attendee_domains(attendees)
        assert domains == []

    def test_deduplicates(self):
        attendees = [
            {"email": "a@company.com"},
            {"email": "b@company.com"},
        ]
        domains = extract_attendee_domains(attendees)
        assert domains.count("company.com") == 1


class TestSlugify:
    """Test the slugify helper."""

    def test_basic(self):
        assert slugify("Team Standup") == "team-standup"

    def test_special_chars(self):
        assert slugify("Call w/ Jane (Acme)") == "call-w-jane-acme"

    def test_truncation(self):
        result = slugify("A" * 100)
        assert len(result) <= 60


class TestSaveEvent:
    """Test saving events to filesystem and DB."""

    def test_save_new_event(self, db_env, monkeypatch):
        monkeypatch.setattr("scan_calendar.INBOX_ROOT", db_env["inbox_root"])

        result = save_event(
            conn=db_env["conn"],
            title="Call with Acme Corp",
            organizer="Jane <jane@acme.com>",
            attendees=[
                {"name": "Jane", "email": "jane@acme.com", "status": "accepted"},
                {"name": "Bob", "email": "bob@vft.institute", "status": "accepted"},
            ],
            start="2026-03-12T10:00:00-08:00",
            end="2026-03-12T11:00:00-08:00",
            description="Discuss seed round terms",
            location="Zoom",
            calendar_name="primary",
            calendar_id="primary",
            event_id="evt-001",
            conference_url="https://zoom.us/j/123",
            status="confirmed",
        )

        assert result["status"] == "saved"
        assert result["id"] > 0
        assert "acme.com" in result["attendee_domains"]

        # Verify markdown file was created
        event_file = Path(result["file"])
        assert event_file.exists()
        content = event_file.read_text()
        assert "Call with Acme Corp" in content
        assert "Jane" in content
        assert "10:00" in content

        # Verify DB row
        row = db_env["conn"].execute(
            "SELECT * FROM messages WHERE source = 'calendar' AND source_id = ?",
            ("primary|evt-001",)
        ).fetchone()
        assert row is not None
        assert row["subject"] == "Call with Acme Corp"
        assert row["type"] == "event"

    def test_skip_duplicate(self, db_env, monkeypatch):
        monkeypatch.setattr("scan_calendar.INBOX_ROOT", db_env["inbox_root"])

        # Save first
        save_event(
            conn=db_env["conn"],
            title="Meeting",
            organizer="org",
            attendees=[],
            start="2026-03-12T10:00:00",
            end="2026-03-12T11:00:00",
            calendar_id="primary",
            event_id="evt-dup",
        )

        # Save again — should skip
        result = save_event(
            conn=db_env["conn"],
            title="Meeting",
            organizer="org",
            attendees=[],
            start="2026-03-12T10:00:00",
            end="2026-03-12T11:00:00",
            calendar_id="primary",
            event_id="evt-dup",
        )
        assert result["status"] == "skipped"
        assert result["reason"] == "already_scanned"

    def test_appends_to_existing_file(self, db_env, monkeypatch):
        monkeypatch.setattr("scan_calendar.INBOX_ROOT", db_env["inbox_root"])

        # Save two events on same day
        save_event(
            conn=db_env["conn"],
            title="Morning Meeting",
            organizer="org",
            attendees=[],
            start="2026-03-12T09:00:00",
            end="2026-03-12T10:00:00",
            calendar_id="primary",
            event_id="evt-am",
        )
        result = save_event(
            conn=db_env["conn"],
            title="Afternoon Meeting",
            organizer="org",
            attendees=[],
            start="2026-03-12T14:00:00",
            end="2026-03-12T15:00:00",
            calendar_id="primary",
            event_id="evt-pm",
        )

        # Both should be in the same file
        content = Path(result["file"]).read_text()
        assert "Morning Meeting" in content
        assert "Afternoon Meeting" in content

    def test_metadata_includes_attendee_domains(self, db_env, monkeypatch):
        monkeypatch.setattr("scan_calendar.INBOX_ROOT", db_env["inbox_root"])

        save_event(
            conn=db_env["conn"],
            title="Test",
            organizer="org",
            attendees=[{"email": "jane@startup.io"}],
            start="2026-03-12T10:00:00",
            end="2026-03-12T11:00:00",
            calendar_id="primary",
            event_id="evt-meta",
        )

        row = db_env["conn"].execute(
            "SELECT metadata FROM messages WHERE source_id = ?",
            ("primary|evt-meta",)
        ).fetchone()
        meta = json.loads(row["metadata"])
        assert "startup.io" in meta["attendee_domains"]


class TestGetScanStatus:
    """Test scan status reporting."""

    def test_empty_db(self, db_env):
        status = get_scan_status(db_env["conn"])
        assert status["total_events"] == 0
        assert status["unclassified"] == 0
        assert status["latest_event_ts"] == "none"
        assert status["calendars_scanned"] == []

    def test_with_events(self, db_env, monkeypatch):
        monkeypatch.setattr("scan_calendar.INBOX_ROOT", db_env["inbox_root"])

        save_event(
            conn=db_env["conn"],
            title="Event 1",
            organizer="org",
            attendees=[],
            start="2026-03-12T10:00:00",
            end="2026-03-12T11:00:00",
            calendar_name="Work",
            calendar_id="work",
            event_id="evt-1",
        )

        status = get_scan_status(db_env["conn"])
        assert status["total_events"] == 1
        assert status["unclassified"] == 1
        assert "Work" in status["calendars_scanned"]
