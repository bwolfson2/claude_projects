"""
VFT Fund Tools — Shared Test Fixtures

Provides fresh databases, temp JSON files, CLI runners, and adversarial test data
for the entire test suite.
"""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# ── Paths ────────────────────────────────────────────────────────────────

# In a git worktree, the source code lives in the main repo
_WORKTREE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path("/Users/nebnoseflow/due_diligences")
if not (REPO_ROOT / "fund" / "metadata" / "init_db.py").exists():
    # Fallback: try worktree root
    REPO_ROOT = _WORKTREE_ROOT
INIT_DB_PATH = REPO_ROOT / "fund" / "metadata" / "init_db.py"

# Add all script directories to sys.path at module load time
_SCRIPT_PATHS = [
    REPO_ROOT / "fund" / "metadata",
    REPO_ROOT / "skills" / "deal-project-classifier" / "scripts",
    REPO_ROOT / "skills" / "reactive-router" / "scripts",
    REPO_ROOT / "skills" / "crm-contacts" / "scripts",
    REPO_ROOT / "skills" / "document-processor" / "scripts",
    REPO_ROOT / "skills" / "sheet-sync" / "scripts",
    REPO_ROOT / "skills" / "comms-hub" / "scripts",
    REPO_ROOT / "skills" / "fund-dealflow-orchestrator" / "scripts",
    REPO_ROOT / "skills" / "message-ingestion" / "scripts",
    REPO_ROOT / "skills" / "project-management" / "scripts",
]
for p in _SCRIPT_PATHS:
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

# ── Adversarial Data ─────────────────────────────────────────────────────

UNICODE_NAMES = [
    "Ünternéhmen GmbH",
    "株式会社テスト",
    "الشركة العربية",
    "🚀 Rocket Co",
    "Ñoño Technologies",
    "Ça Va Startup",
]

SQL_INJECTIONS = [
    "'; DROP TABLE messages; --",
    '" OR 1=1 --',
    "<script>alert(1)</script>",
    "Robert'); DROP TABLE students;--",
    "1; UPDATE messages SET classified=1 WHERE 1=1;--",
]

MALFORMED_EMAILS = [
    "not-an-email",
    "@domain.com",
    "user@",
    "user@@domain.com",
    "",
    "   ",
    "user@.com",
    "user@domain..com",
]

BOUNDARY_VALUES = {
    "confidence": [-1.0, 0.0, 0.001, 0.5, 0.999, 1.0, 1.5, 999.0],
    "body_short": "",
    "body_long": "x" * 100_000,
    "subject_long": "S" * 10_000,
    "slug_long": "a" * 200,
}


# ── Database Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def fresh_db(tmp_path):
    """Create a fresh SQLite database using init_db.py's schema."""
    db_path = str(tmp_path / "ingestion.db")
    from init_db import init_db
    conn = init_db(db_path)
    yield conn, db_path
    conn.close()


@pytest.fixture
def populated_db(fresh_db):
    """Seed database with 10 realistic messages across sources."""
    conn, db_path = fresh_db
    now = datetime.now()

    messages = [
        # Outlook messages
        ("outlook", "msg-001", "email", "ceo@midbound.com", '["fund@vc.com"]',
         "Midbound Series A Update", "Hi, here's our latest traction update...",
         (now - timedelta(hours=2)).isoformat(), "inbox", "[]", "[]"),
        ("outlook", "msg-002", "email", "jane@acmecorp.com", '["fund@vc.com"]',
         "Term Sheet - Acme Corp", "Please find attached our term sheet for review.",
         (now - timedelta(hours=4)).isoformat(), "inbox",
         '[{"name": "term_sheet.pdf", "path": "/tmp/term_sheet.pdf"}]', "[]"),
        ("outlook", "msg-003", "email", "unknown@newstartup.io", '["fund@vc.com"]',
         "Intro: NewStartup - AI for Healthcare", "I'd like to introduce you to NewStartup...",
         (now - timedelta(hours=6)).isoformat(), "inbox", "[]", "[]"),
        ("outlook", "msg-004", "email", "legal@lawfirm.com", '["fund@vc.com"]',
         "Fund Formation Documents", "Please review the attached partnership agreement.",
         (now - timedelta(hours=8)).isoformat(), "inbox", "[]", "[]"),
        # Slack messages
        ("slack", "slack-001", "message", "john.smith", '[]',
         "Deal Discussion", "What do we think about the Midbound deal?",
         (now - timedelta(hours=1)).isoformat(), "#deals", "[]", "[]"),
        ("slack", "slack-002", "message", "sarah.jones", '[]',
         "Meeting Tomorrow", "Don't forget the Acme Corp meeting tomorrow at 2pm.",
         (now - timedelta(hours=3)).isoformat(), "#general", "[]", "[]"),
        # Signal messages
        ("signal", "sig-001", "message", "+15551234567", '[]',
         None, "Hey, got the dataroom link for WidgetCo. Check email.",
         (now - timedelta(hours=5)).isoformat(), "direct", "[]", "[]"),
        # Granola transcripts
        ("granola", "transcript-001", "transcript", "Granola Bot", '[]',
         "Midbound Intro Call", "Meeting notes from the intro call with Midbound CEO...",
         (now - timedelta(days=1)).isoformat(), None, "[]", "[]"),
        ("granola", "transcript-002", "transcript", "Granola Bot", '[]',
         "Team Sync - Weekly", "Weekly standup notes covering pipeline review...",
         (now - timedelta(days=2)).isoformat(), None, "[]", "[]"),
        # Web scrape
        ("web", "web-001", "scrape", "scraper", '[]',
         "TechCrunch: NewStartup raises $5M", "NewStartup announced a $5M seed round...",
         (now - timedelta(days=3)).isoformat(), "https://techcrunch.com", "[]", "[]"),
    ]

    for msg in messages:
        conn.execute(
            """INSERT INTO messages
               (source, source_id, type, sender, recipients, subject, body,
                timestamp, channel, attachments, project_tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            msg,
        )

    # Mark some as classified
    conn.execute("UPDATE messages SET classified = 1 WHERE id IN (1, 2, 5)")
    # Mark one as routed
    conn.execute("UPDATE messages SET routed_at = ? WHERE id = 1",
                 (now.isoformat(),))

    # Add some classification log entries
    conn.execute(
        """INSERT INTO classification_log
           (source_type, source_id, matched_slug, match_type, confidence, rule_hits)
           VALUES ('message', 1, 'midbound', 'deal', 0.95, '{"domain_match": "midbound.com"}')""")
    conn.execute(
        """INSERT INTO classification_log
           (source_type, source_id, matched_slug, match_type, confidence, rule_hits)
           VALUES ('message', 2, 'acme-corp', 'deal', 0.90, '{"subject_match": true}')""")

    conn.commit()
    yield conn, db_path


# ── JSON File Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def deals_json(tmp_path):
    """Create a temp deals.json with 3 companies in the expected format."""
    data = {
        "companies": [
            {
                "slug": "midbound",
                "company_name": "Midbound",
                "status": "active",
                "stage": "diligence",
                "owner": "fund",
                "sector": "SaaS",
                "domains": ["midbound.com"],
                "contact_emails": ["ceo@midbound.com", "cto@midbound.com"],
                "last_touch": "2026-03-10",
                "keywords": ["sales", "automation"],
            },
            {
                "slug": "acme-corp",
                "company_name": "Acme Corp",
                "status": "active",
                "stage": "sourced",
                "owner": "fund",
                "sector": "Fintech",
                "domains": ["acmecorp.com"],
                "contact_emails": ["jane@acmecorp.com"],
                "last_touch": "2026-03-08",
            },
            {
                "slug": "oldco",
                "company_name": "OldCo",
                "status": "passed",
                "stage": "IC",
                "owner": "fund",
                "sector": "Hardware",
                "domains": ["oldco.com"],
                "contact_emails": [],
                "last_touch": "2026-01-15",
            },
        ],
        "last_updated": "2026-03-10",
    }
    path = tmp_path / "fund" / "crm" / "deals.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path


@pytest.fixture
def projects_json(tmp_path):
    """Create a temp projects.json with 3 projects."""
    data = {
        "projects": [
            {
                "slug": "fund-ops",
                "project_name": "Fund Operations",
                "name": "Fund Operations",
                "category": "operations",
                "status": "active",
                "keywords": ["admin", "legal"],
                "contact_emails": ["legal@lawfirm.com"],
            },
            {
                "slug": "hiring-eng",
                "project_name": "Engineering Hiring",
                "name": "Engineering Hiring",
                "category": "hiring",
                "status": "active",
                "keywords": ["recruitment", "engineering"],
                "contact_emails": [],
            },
            {
                "slug": "old-research",
                "project_name": "Old Research Project",
                "name": "Old Research Project",
                "category": "research",
                "status": "archived",
                "keywords": ["research"],
                "contact_emails": [],
            },
        ],
        "last_updated": "2026-03-10",
    }
    path = tmp_path / "projects" / "projects.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path


@pytest.fixture
def contacts_json(tmp_path):
    """Create a temp contacts.json with sample contacts."""
    data = [
        {
            "name": "Jane Smith",
            "email": "jane@acmecorp.com",
            "company": "Acme Corp",
            "title": "CEO",
            "tags": ["founder", "fintech"],
            "deal_slugs": ["acme-corp"],
            "project_slugs": [],
            "first_seen": "2026-02-01",
            "last_contacted": "2026-03-08",
            "source": "outlook",
        },
        {
            "name": "Bob CEO",
            "email": "ceo@midbound.com",
            "company": "Midbound",
            "title": "CEO",
            "tags": ["founder"],
            "deal_slugs": ["midbound"],
            "project_slugs": [],
            "first_seen": "2026-01-15",
            "last_contacted": "2026-03-10",
            "source": "outlook",
        },
    ]
    path = tmp_path / "fund" / "crm" / "contacts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path


@pytest.fixture
def empty_deals_json(tmp_path):
    """Empty deals.json."""
    data = {"companies": []}
    path = tmp_path / "fund" / "crm" / "deals.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path


@pytest.fixture
def empty_projects_json(tmp_path):
    """Empty projects.json."""
    data = {"projects": []}
    path = tmp_path / "projects" / "projects.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path


# ── VFT Environment Fixture ─────────────────────────────────────────────

@pytest.fixture
def vft_env(tmp_path, fresh_db, deals_json, projects_json):
    """Set up a complete VFT environment with DB, JSON files, and env vars."""
    conn, db_path = fresh_db

    # Build directory structure expected by scripts
    db_dir = tmp_path / "fund" / "metadata" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)

    # Copy DB to expected location
    import shutil
    target_db = db_dir / "ingestion.db"
    conn.close()
    shutil.copy(db_path, str(target_db))

    # Reopen from new location
    new_conn = sqlite3.connect(str(target_db))
    new_conn.execute("PRAGMA journal_mode=OFF")
    new_conn.row_factory = sqlite3.Row

    # Set environment
    old_env = os.environ.get("VFT_REPO_ROOT")
    os.environ["VFT_REPO_ROOT"] = str(tmp_path)

    yield {
        "root": tmp_path,
        "conn": new_conn,
        "db_path": str(target_db),
        "deals_path": deals_json,
        "projects_path": projects_json,
    }

    new_conn.close()
    if old_env:
        os.environ["VFT_REPO_ROOT"] = old_env
    else:
        os.environ.pop("VFT_REPO_ROOT", None)


# ── CLI Runner ───────────────────────────────────────────────────────────

def run_cli(script_path, args, env_override=None):
    """Run a Python script as subprocess and capture output.

    Returns (returncode, stdout_text, stderr_text).
    stdout is attempted to be parsed as JSON.
    """
    env = os.environ.copy()
    if env_override:
        env.update(env_override)

    result = subprocess.run(
        [sys.executable, str(script_path)] + args,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def parse_json_output(stdout):
    """Parse JSON from CLI stdout, handling multi-line output."""
    # Find the last valid JSON object in output
    lines = stdout.strip().split("\n")
    for i in range(len(lines)):
        try:
            return json.loads("\n".join(lines[i:]))
        except json.JSONDecodeError:
            continue
    # Try the whole thing
    return json.loads(stdout)


# ── Row Insertion Helpers ────────────────────────────────────────────────

def insert_message(conn, **overrides):
    """Insert a message with sensible defaults. Returns the new message ID."""
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


def insert_classification(conn, **overrides):
    """Insert a classification_log entry. Returns the new ID."""
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


def insert_contact(conn, **overrides):
    """Insert a contact row. Returns the new ID."""
    defaults = {
        "name": "Test User",
        "email": f"test-{datetime.now().timestamp()}@example.com",
        "company": "Test Co",
        "source": "outlook",
    }
    defaults.update(overrides)

    cursor = conn.execute(
        """INSERT INTO contacts (name, email, company, source)
           VALUES (:name, :email, :company, :source)""",
        defaults,
    )
    conn.commit()
    return cursor.lastrowid


def get_all_rows(conn, table):
    """Return all rows from a table as list of dicts."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    return [dict(r) for r in rows]
