#!/usr/bin/env python3
"""
VFT Ingestion Database — Schema Initializer

Creates and migrates the SQLite metadata store used by the email-scanner,
transcript-ingestion, and deal-project-classifier skills.

Usage:
    python init_db.py                  # creates/migrates ingestion.db in same dir
    python init_db.py --db /path/to.db # explicit path
"""

import argparse
import os
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 4

DDL = """
-- ============================================================
-- VFT Ingestion Metadata Store  (schema v{version})
-- ============================================================

-- Legacy: Emails pulled from Outlook via Claude in Chrome
CREATE TABLE IF NOT EXISTS emails (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    outlook_id      TEXT UNIQUE,
    subject         TEXT NOT NULL,
    sender          TEXT NOT NULL,
    sender_domain   TEXT,
    recipients      TEXT,
    date            TEXT NOT NULL,
    body_preview    TEXT,
    folder_saved_to TEXT,
    raw_path        TEXT,
    has_attachments INTEGER DEFAULT 0,
    attachment_paths TEXT,
    classified      INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Legacy: Transcripts pulled from Granola MCP connector
CREATE TABLE IF NOT EXISTS transcripts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    granola_id      TEXT UNIQUE,
    title           TEXT NOT NULL,
    participants    TEXT,
    date            TEXT NOT NULL,
    summary         TEXT,
    raw_path        TEXT,
    classified      INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ============================================================
-- Unified Messages Table (v2) — single query surface for all sources
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL CHECK (source IN ('outlook', 'slack', 'whatsapp', 'signal', 'granola', 'web', 'calendar', 'file_intake')),
    source_id       TEXT NOT NULL,                       -- original dedup key
    type            TEXT NOT NULL CHECK (type IN ('email', 'message', 'transcript', 'thread', 'document', 'scrape')),
    sender          TEXT,
    recipients      TEXT,                                -- JSON array
    subject         TEXT,
    body            TEXT,
    timestamp       TEXT NOT NULL,                       -- ISO-8601
    channel         TEXT,                                -- inbox, #channel, group-name, direct, url
    attachments     TEXT DEFAULT '[]',                   -- JSON array of {{name, path}}
    project_tags    TEXT DEFAULT '[]',                   -- JSON array of project/deal slugs
    raw_path        TEXT,
    metadata        TEXT DEFAULT '{{}}',                 -- JSON for source-specific extras
    classified      INTEGER DEFAULT 0,
    routed_at       TEXT,                              -- set by reactive-router when processed
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(source, source_id)
);

-- Company matching index (rebuilt from deals.json)
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

-- Project matching index (rebuilt from projects.json)
CREATE TABLE IF NOT EXISTS project_index (
    project_slug    TEXT PRIMARY KEY,
    project_name    TEXT NOT NULL,
    keywords        TEXT,
    contact_emails  TEXT,
    category        TEXT,
    status          TEXT
);

-- Classification audit log
CREATE TABLE IF NOT EXISTS classification_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type     TEXT NOT NULL CHECK (source_type IN ('email', 'transcript', 'message')),
    source_id       INTEGER NOT NULL,
    matched_slug    TEXT,
    match_type      TEXT CHECK (match_type IN ('deal', 'project', 'new_deal', 'new_project', 'unclassified')),
    confidence      REAL DEFAULT 0.0,
    rule_hits       TEXT,
    auto_created    INTEGER DEFAULT 0,
    reviewed        INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Dedup guard — prevents re-processing
CREATE TABLE IF NOT EXISTS processed_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type     TEXT NOT NULL CHECK (source_type IN ('email', 'transcript', 'message')),
    source_id       INTEGER NOT NULL,
    action_taken    TEXT,
    timestamp       TEXT DEFAULT (datetime('now')),
    UNIQUE(source_type, source_id, action_taken)
);

-- Schema version tracker
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- ============================================================
-- Document Processing Tables (schema v3)
-- ============================================================

-- Raw extracted text per page (the "symbolic handle" for RLM processing)
CREATE TABLE IF NOT EXISTS document_pages (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path           TEXT NOT NULL,
    dataroom_slug       TEXT NOT NULL,
    page_number         INTEGER NOT NULL,
    total_pages         INTEGER DEFAULT 0,
    text_content        TEXT,
    char_count          INTEGER DEFAULT 0,
    extraction_method   TEXT,
    extraction_quality  REAL DEFAULT 1.0,
    metadata            TEXT DEFAULT '{{}}'  ,
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE(file_path, dataroom_slug, page_number)
);

-- Structured extractions from RLM recursive processing
CREATE TABLE IF NOT EXISTS document_extractions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path           TEXT NOT NULL,
    dataroom_slug       TEXT NOT NULL,
    extraction_type     TEXT NOT NULL,
    extraction_key      TEXT,
    content             TEXT NOT NULL,
    page_range          TEXT,
    confidence          REAL DEFAULT 0.0,
    tokens_used         INTEGER DEFAULT 0,
    cost_usd            REAL DEFAULT 0.0,
    model_used          TEXT,
    parent_id           INTEGER,
    created_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (parent_id) REFERENCES document_extractions(id)
);

-- Processing job tracker for dedup and cost control
CREATE TABLE IF NOT EXISTS document_jobs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    dataroom_slug       TEXT NOT NULL,
    file_path           TEXT,
    job_type            TEXT NOT NULL,
    status              TEXT DEFAULT 'pending',
    total_pages         INTEGER DEFAULT 0,
    pages_processed     INTEGER DEFAULT 0,
    total_tokens        INTEGER DEFAULT 0,
    total_cost_usd      REAL DEFAULT 0.0,
    error_message       TEXT,
    started_at          TEXT,
    completed_at        TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE(dataroom_slug, file_path, job_type)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_doc_pages_file ON document_pages(file_path, dataroom_slug);
CREATE INDEX IF NOT EXISTS idx_doc_pages_dataroom ON document_pages(dataroom_slug);
CREATE INDEX IF NOT EXISTS idx_doc_extractions_file ON document_extractions(file_path, dataroom_slug);
CREATE INDEX IF NOT EXISTS idx_doc_extractions_type ON document_extractions(extraction_type);
CREATE INDEX IF NOT EXISTS idx_doc_extractions_key ON document_extractions(extraction_key);
CREATE INDEX IF NOT EXISTS idx_doc_jobs_dataroom ON document_jobs(dataroom_slug);
CREATE INDEX IF NOT EXISTS idx_doc_jobs_status ON document_jobs(status);

-- ============================================================
-- CRM Contacts Table (v4) — unified contacts across all platforms
-- ============================================================
CREATE TABLE IF NOT EXISTS contacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    company         TEXT,
    title           TEXT,
    slack_handle    TEXT,
    whatsapp_id     TEXT,
    signal_id       TEXT,
    linkedin_url    TEXT,
    tags            TEXT DEFAULT '[]',                   -- JSON: ["founder", "investor"]
    context         TEXT,                                -- relationship notes
    deal_slugs      TEXT DEFAULT '[]',                   -- JSON: linked deals
    project_slugs   TEXT DEFAULT '[]',                   -- JSON: linked projects
    first_seen      TEXT,                                -- ISO timestamp
    last_contacted  TEXT,                                -- most recent interaction
    source          TEXT,                                -- platform first seen on
    metadata        TEXT DEFAULT '{{}}',                 -- JSON extras
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(email)
);
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company);
CREATE INDEX IF NOT EXISTS idx_contacts_last_contacted ON contacts(last_contacted);
CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(name);

CREATE INDEX IF NOT EXISTS idx_emails_classified ON emails(classified);
CREATE INDEX IF NOT EXISTS idx_emails_sender_domain ON emails(sender_domain);
CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(date);
CREATE INDEX IF NOT EXISTS idx_transcripts_classified ON transcripts(classified);
CREATE INDEX IF NOT EXISTS idx_transcripts_date ON transcripts(date);
CREATE INDEX IF NOT EXISTS idx_messages_source ON messages(source);
CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_classified ON messages(classified);
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel);
CREATE INDEX IF NOT EXISTS idx_classification_log_source ON classification_log(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_classification_log_slug ON classification_log(matched_slug);
CREATE INDEX IF NOT EXISTS idx_processed_items_source ON processed_items(source_type, source_id);
""".format(version=SCHEMA_VERSION)


def init_db(db_path: str) -> sqlite3.Connection:
    """Create or migrate the ingestion database."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=OFF")  # No journal files — required for GDrive Desktop FS
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(DDL)

    # Track schema version
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    conn.commit()
    print(f"[VFT] Database initialized at {db_path} (schema v{SCHEMA_VERSION})")
    return conn


def get_db_path(override: str = None) -> str:
    """Resolve the database path."""
    if override:
        return override
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "ingestion.db")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize VFT ingestion database")
    parser.add_argument("--db", type=str, help="Path to database file")
    args = parser.parse_args()

    db_path = get_db_path(args.db)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = init_db(db_path)

    # Print table summary
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    print(f"[VFT] Tables: {', '.join(tables)}")
    conn.close()
