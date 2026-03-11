#!/usr/bin/env python3
"""
VFT Document Processor — Query Interface

Provides a query API for specialist skills to access extracted document content
and structured extractions from the document_pages and document_extractions tables.

Usage:
    python query_documents.py --dataroom midbound_dataroom --type table
    python query_documents.py --dataroom midbound_dataroom --key revenue_metrics
    python query_documents.py --dataroom midbound_dataroom --search "valuation cap"
    python query_documents.py --dataroom midbound_dataroom --file "Legal/safe.pdf" --pages 1-3
    python query_documents.py --dataroom midbound_dataroom --stats
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.row_factory = sqlite3.Row
    return conn


def query_extractions(
    conn: sqlite3.Connection,
    dataroom_slug: str,
    extraction_type: str = None,
    extraction_key: str = None,
    file_path: str = None,
    min_confidence: float = 0.0,
) -> list[dict]:
    """Query document extractions for specialist skills.

    Returns list of extraction records with parsed JSON content.
    """
    conditions = ["dataroom_slug = ?"]
    params = [dataroom_slug]

    if extraction_type:
        conditions.append("extraction_type = ?")
        params.append(extraction_type)
    if extraction_key:
        conditions.append("extraction_key LIKE ?")
        params.append(f"%{extraction_key}%")
    if file_path:
        conditions.append("file_path LIKE ?")
        params.append(f"%{file_path}%")
    if min_confidence > 0:
        conditions.append("confidence >= ?")
        params.append(min_confidence)

    where = " AND ".join(conditions)
    rows = conn.execute(
        f"""SELECT id, file_path, extraction_type, extraction_key, content,
                   page_range, confidence, tokens_used, cost_usd, model_used, created_at
            FROM document_extractions
            WHERE {where}
            ORDER BY created_at DESC""",
        params,
    ).fetchall()

    results = []
    for r in rows:
        try:
            content = json.loads(r["content"])
        except (json.JSONDecodeError, TypeError):
            content = r["content"]

        results.append({
            "id": r["id"],
            "file_path": r["file_path"],
            "extraction_type": r["extraction_type"],
            "extraction_key": r["extraction_key"],
            "content": content,
            "page_range": r["page_range"],
            "confidence": r["confidence"],
            "tokens_used": r["tokens_used"],
            "cost_usd": r["cost_usd"],
            "model_used": r["model_used"],
            "created_at": r["created_at"],
        })

    return results


def get_document_text(
    conn: sqlite3.Connection,
    file_path: str,
    dataroom_slug: str,
    page_start: int = None,
    page_end: int = None,
) -> str:
    """Get raw extracted text for a file or page range.

    Used by RLM loop and specialist skills for direct document access.
    """
    conditions = ["file_path = ?", "dataroom_slug = ?"]
    params = [file_path, dataroom_slug]

    if page_start is not None:
        conditions.append("page_number >= ?")
        params.append(page_start)
    if page_end is not None:
        conditions.append("page_number <= ?")
        params.append(page_end)

    where = " AND ".join(conditions)
    rows = conn.execute(
        f"""SELECT page_number, text_content FROM document_pages
            WHERE {where}
            ORDER BY page_number""",
        params,
    ).fetchall()

    parts = []
    for r in rows:
        parts.append(f"--- Page {r['page_number']} ---")
        parts.append(r["text_content"] or "(empty)")

    return "\n\n".join(parts)


def search_documents(
    conn: sqlite3.Connection,
    dataroom_slug: str,
    query: str,
    max_results: int = 20,
) -> list[dict]:
    """Full-text search across all extracted pages in a dataroom.

    Returns matching pages with file path, page number, and snippet.
    """
    rows = conn.execute(
        """SELECT file_path, page_number, text_content
           FROM document_pages
           WHERE dataroom_slug = ? AND text_content LIKE ?
           ORDER BY file_path, page_number""",
        (dataroom_slug, f"%{query}%"),
    ).fetchall()

    results = []
    for r in rows[:max_results]:
        text = r["text_content"] or ""
        idx = text.lower().find(query.lower())
        if idx >= 0:
            start = max(0, idx - 100)
            end = min(len(text), idx + len(query) + 100)
            snippet = text[start:end].strip()
        else:
            snippet = text[:200].strip()

        results.append({
            "file_path": r["file_path"],
            "page": r["page_number"],
            "snippet": snippet,
        })

    return results


def get_dataroom_stats(conn: sqlite3.Connection, dataroom_slug: str) -> dict:
    """Get processing statistics for a dataroom."""
    pages = conn.execute(
        """SELECT COUNT(*) as count, SUM(char_count) as total_chars,
                  COUNT(DISTINCT file_path) as file_count
           FROM document_pages WHERE dataroom_slug = ?""",
        (dataroom_slug,),
    ).fetchone()

    extractions = conn.execute(
        """SELECT COUNT(*) as count, SUM(tokens_used) as total_tokens,
                  SUM(cost_usd) as total_cost
           FROM document_extractions WHERE dataroom_slug = ?""",
        (dataroom_slug,),
    ).fetchone()

    # Extraction keys breakdown
    keys = conn.execute(
        """SELECT extraction_key, COUNT(*) as count
           FROM document_extractions
           WHERE dataroom_slug = ?
           GROUP BY extraction_key
           ORDER BY count DESC""",
        (dataroom_slug,),
    ).fetchall()

    # Methods breakdown
    methods = conn.execute(
        """SELECT extraction_method, COUNT(*) as count
           FROM document_pages
           WHERE dataroom_slug = ?
           GROUP BY extraction_method""",
        (dataroom_slug,),
    ).fetchall()

    return {
        "dataroom": dataroom_slug,
        "pages": {
            "total": pages["count"],
            "total_chars": pages["total_chars"] or 0,
            "files": pages["file_count"],
        },
        "extractions": {
            "total": extractions["count"],
            "total_tokens": extractions["total_tokens"] or 0,
            "total_cost_usd": round(extractions["total_cost"] or 0, 6),
        },
        "extraction_keys": {r["extraction_key"]: r["count"] for r in keys},
        "extraction_methods": {r["extraction_method"]: r["count"] for r in methods},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Document Query Interface")
    parser.add_argument("--dataroom", required=True, help="Dataroom slug")
    parser.add_argument("--type", dest="extraction_type", help="Filter by extraction type")
    parser.add_argument("--key", dest="extraction_key", help="Filter by extraction key")
    parser.add_argument("--file", help="Filter by file path")
    parser.add_argument("--pages", help="Page range (e.g. 1-5)")
    parser.add_argument("--search", help="Full-text search query")
    parser.add_argument("--stats", action="store_true", help="Show dataroom statistics")
    parser.add_argument("--min-confidence", type=float, default=0.0)
    parser.add_argument("--db", type=str, help="Path to ingestion.db")
    args = parser.parse_args()

    if args.db:
        conn = sqlite3.connect(args.db)
        conn.execute("PRAGMA journal_mode=OFF")
        conn.row_factory = sqlite3.Row
    else:
        conn = get_db()

    if args.stats:
        result = get_dataroom_stats(conn, args.dataroom)
        print(json.dumps(result, indent=2))

    elif args.search:
        results = search_documents(conn, args.dataroom, args.search)
        print(json.dumps({"query": args.search, "results": results}, indent=2))

    elif args.file and args.pages:
        # Parse page range
        if "-" in args.pages:
            start, end = args.pages.split("-")
            text = get_document_text(conn, args.file, args.dataroom, int(start), int(end))
        else:
            text = get_document_text(conn, args.file, args.dataroom, int(args.pages), int(args.pages))
        print(text)

    elif args.file:
        text = get_document_text(conn, args.file, args.dataroom)
        print(text)

    else:
        results = query_extractions(
            conn, args.dataroom,
            extraction_type=args.extraction_type,
            extraction_key=args.extraction_key,
            min_confidence=args.min_confidence,
        )
        print(json.dumps(results, indent=2))

    conn.close()
