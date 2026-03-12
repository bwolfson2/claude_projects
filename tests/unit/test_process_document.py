#!/usr/bin/env python3
"""Unit tests for skills/document-processor/scripts/process_document.py"""

import json
import sqlite3
import sys
import types
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path("/Users/nebnoseflow/due_diligences")
if not REPO_ROOT.exists():
    REPO_ROOT = Path(__file__).resolve().parents[4]

SCRIPT_DIR = REPO_ROOT / "skills" / "document-processor" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import process_document  # noqa: E402

DOC_SCHEMA = """
CREATE TABLE IF NOT EXISTS document_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    dataroom_slug TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    total_pages INTEGER,
    text_content TEXT,
    char_count INTEGER DEFAULT 0,
    extraction_method TEXT,
    extraction_quality REAL,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(file_path, dataroom_slug, page_number)
);
CREATE TABLE IF NOT EXISTS document_extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    dataroom_slug TEXT NOT NULL,
    extraction_type TEXT,
    extraction_key TEXT NOT NULL,
    content TEXT,
    page_range TEXT,
    confidence REAL DEFAULT 0.0,
    tokens_used INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    model_used TEXT,
    parent_id INTEGER REFERENCES document_extractions(id),
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS document_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataroom_slug TEXT NOT NULL,
    file_path TEXT,
    job_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    total_pages INTEGER DEFAULT 0,
    pages_processed INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(dataroom_slug, file_path, job_type)
);
"""


@pytest.fixture
def db(tmp_path):
    """Create an in-memory style temp DB and patch process_document.get_db."""
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.executescript(DOC_SCHEMA)
    conn.commit()

    def _get_db():
        c = sqlite3.connect(str(db_file))
        c.execute("PRAGMA journal_mode=OFF")
        c.execute("PRAGMA foreign_keys=ON")
        c.row_factory = sqlite3.Row
        return c

    with patch.object(process_document, "get_db", _get_db):
        yield conn
    conn.close()


def _seed_pages(conn, file_path="doc.pdf", dataroom="dr1", pages=None):
    """Insert test document pages."""
    if pages is None:
        pages = [
            (1, "This is page one about valuation.", 33, "pdfplumber", 0.95, "{}"),
            (2, "Page two discusses revenue metrics.", 35, "pdfplumber", 0.90, "{}"),
            (3, "Third page covers governance and cap table.", 43, "pdfplumber", 0.88, "{}"),
        ]
    for pg_num, text, chars, method, quality, meta in pages:
        conn.execute(
            """INSERT INTO document_pages
               (file_path, dataroom_slug, page_number, total_pages,
                text_content, char_count, extraction_method, extraction_quality, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_path, dataroom, pg_num, len(pages), text, chars, method, quality, meta),
        )
    conn.commit()


# ── cmd_info tests ─────────────────────────────────────────────────────


class TestCmdInfo:
    def test_info_with_pages(self, db, capsys):
        _seed_pages(db)
        args = Namespace(file="doc.pdf", dataroom="dr1")
        process_document.cmd_info(args)
        out = json.loads(capsys.readouterr().out)
        assert out["page_count"] == 3
        assert out["total_chars"] == 33 + 35 + 43
        assert len(out["pages"]) == 3

    def test_info_no_pages(self, db, capsys):
        args = Namespace(file="missing.pdf", dataroom="dr1")
        process_document.cmd_info(args)
        out = json.loads(capsys.readouterr().out)
        assert "error" in out


# ── cmd_slice tests ────────────────────────────────────────────────────


class TestCmdSlice:
    def test_slice_single_page(self, db, capsys):
        _seed_pages(db)
        args = Namespace(file="doc.pdf", dataroom="dr1", pages="2")
        process_document.cmd_slice(args)
        output = capsys.readouterr().out
        assert "Page 2" in output
        assert "revenue metrics" in output

    def test_slice_page_range(self, db, capsys):
        _seed_pages(db)
        args = Namespace(file="doc.pdf", dataroom="dr1", pages="1-3")
        process_document.cmd_slice(args)
        output = capsys.readouterr().out
        assert "Page 1" in output
        assert "Page 2" in output
        assert "Page 3" in output

    def test_slice_out_of_range(self, db, capsys):
        _seed_pages(db)
        args = Namespace(file="doc.pdf", dataroom="dr1", pages="99-100")
        process_document.cmd_slice(args)
        output = capsys.readouterr().out
        # No pages returned; output should be empty or whitespace
        assert "Page 99" not in output


# ── cmd_search tests ───────────────────────────────────────────────────


class TestCmdSearch:
    def test_search_matching(self, db, capsys):
        _seed_pages(db)
        args = Namespace(file="doc.pdf", dataroom="dr1", query="valuation", max_results=10)
        process_document.cmd_search(args)
        out = json.loads(capsys.readouterr().out)
        assert out["total_matches"] >= 1
        assert "valuation" in out["results"][0]["snippet"].lower()

    def test_search_no_match(self, db, capsys):
        _seed_pages(db)
        args = Namespace(file="doc.pdf", dataroom="dr1", query="xyznonexistent", max_results=10)
        process_document.cmd_search(args)
        out = json.loads(capsys.readouterr().out)
        assert out["total_matches"] == 0
        assert out["results"] == []

    def test_search_max_results(self, db, capsys):
        # Seed 5 pages all containing "important"
        pages = [
            (i, f"This important text is on page {i}", 30, "pdf", 0.9, "{}")
            for i in range(1, 6)
        ]
        _seed_pages(db, pages=pages)
        args = Namespace(file="doc.pdf", dataroom="dr1", query="important", max_results=2)
        process_document.cmd_search(args)
        out = json.loads(capsys.readouterr().out)
        assert out["total_matches"] == 5
        assert len(out["results"]) == 2

    def test_search_sql_injection(self, db, capsys):
        _seed_pages(db)
        args = Namespace(
            file="doc.pdf", dataroom="dr1",
            query="'; DROP TABLE document_pages; --", max_results=10,
        )
        process_document.cmd_search(args)
        out = json.loads(capsys.readouterr().out)
        assert out["total_matches"] == 0
        # Table still exists
        row = db.execute(
            "SELECT count(*) as cnt FROM document_pages"
        ).fetchone()
        assert row["cnt"] == 3

    def test_search_unicode(self, db, capsys):
        pages = [
            (1, "Revenue was 500 EUR. See notes.", 40, "pdf", 0.9, "{}"),
        ]
        _seed_pages(db, pages=pages)
        args = Namespace(file="doc.pdf", dataroom="dr1", query="EUR", max_results=10)
        process_document.cmd_search(args)
        out = json.loads(capsys.readouterr().out)
        assert out["total_matches"] == 1


# ── cmd_tasks tests ────────────────────────────────────────────────────


class TestCmdTasks:
    def test_tasks_no_filter(self, capsys):
        args = Namespace(category=None)
        process_document.cmd_tasks(args)
        out = json.loads(capsys.readouterr().out)
        assert "governance" in out
        assert "finance" in out
        assert "legal" in out

    def test_tasks_with_category(self, capsys):
        args = Namespace(category="finance")
        process_document.cmd_tasks(args)
        out = json.loads(capsys.readouterr().out)
        assert out["category"] == "finance"
        task_names = [t["task"] for t in out["tasks"]]
        assert "extract_revenue_metrics" in task_names


# ── cmd_store tests ────────────────────────────────────────────────────


class TestCmdStore:
    def test_store_valid_json(self, db, capsys):
        content = json.dumps({"valuation_cap": "10M", "discount": "20%"})
        args = Namespace(
            file="doc.pdf", dataroom="dr1", key="safe_terms",
            content=content, type="extraction", page_range="1-2", confidence=0.95,
        )
        process_document.cmd_store(args)
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "stored"
        assert isinstance(out["extraction_id"], int)

        # Verify in DB
        row = db.execute(
            "SELECT * FROM document_extractions WHERE id = ?",
            (out["extraction_id"],),
        ).fetchone()
        assert row is not None
        assert json.loads(row["content"])["valuation_cap"] == "10M"

    def test_store_plain_text(self, db, capsys):
        args = Namespace(
            file="doc.pdf", dataroom="dr1", key="raw_note",
            content="This is plain text, not JSON.",
            type="extraction", page_range=None, confidence=1.0,
        )
        process_document.cmd_store(args)
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "stored"

        row = db.execute(
            "SELECT content FROM document_extractions WHERE id = ?",
            (out["extraction_id"],),
        ).fetchone()
        assert row["content"] == "This is plain text, not JSON."


# ── cmd_list_files tests ──────────────────────────────────────────────


class TestCmdListFiles:
    def test_list_files_multiple(self, db, capsys):
        _seed_pages(db, file_path="alpha.pdf", dataroom="dr1")
        _seed_pages(db, file_path="beta.pdf", dataroom="dr1", pages=[
            (1, "Beta content", 12, "ocr", 0.7, "{}"),
        ])
        args = Namespace(dataroom="dr1")
        process_document.cmd_list_files(args)
        out = json.loads(capsys.readouterr().out)
        assert out["file_count"] == 2
        paths = [f["file_path"] for f in out["files"]]
        assert "alpha.pdf" in paths
        assert "beta.pdf" in paths

    def test_list_files_empty(self, db, capsys):
        args = Namespace(dataroom="empty_dr")
        process_document.cmd_list_files(args)
        out = json.loads(capsys.readouterr().out)
        assert out["file_count"] == 0
        assert out["files"] == []
