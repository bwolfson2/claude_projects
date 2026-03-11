#!/usr/bin/env python3
"""
VFT Document Processor — RLM Document Access CLI

Provides subcommands for Claude Code to drive RLM-style document processing.
Instead of calling the Claude API directly, Claude Code uses its own reasoning
to navigate documents via these commands:

    python process_document.py info   --file X --dataroom Y
    python process_document.py slice  --file X --dataroom Y --pages 1-3
    python process_document.py search --file X --dataroom Y --query "valuation"
    python process_document.py tasks  --category governance
    python process_document.py store  --file X --dataroom Y --key safe_terms --content '{...}'
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, UTC
from pathlib import Path

REPO_ROOT = Path(os.environ.get("VFT_REPO_ROOT",
    Path(__file__).resolve().parents[3]))
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"

# Predefined extraction schemas by document category
EXTRACTION_TASKS = {
    "governance": [
        {
            "task": "extract_cap_table",
            "description": "Extract cap table: investors, amounts, instruments, dates, ownership percentages",
            "schema": {"investors": [], "amounts": [], "instruments": [], "dates": [], "ownership_pct": []},
        },
        {
            "task": "extract_safe_terms",
            "description": "Extract SAFE/note terms: valuation cap, discount, investor, amount, date",
            "schema": {"valuation_cap": "", "discount": "", "investor": "", "amount": "", "date": "", "type": ""},
        },
    ],
    "finance": [
        {
            "task": "extract_revenue_metrics",
            "description": "Extract revenue metrics: ARR, MRR, growth rate, period, customer count",
            "schema": {"arr": "", "mrr": "", "growth_rate": "", "period": "", "customer_count": ""},
        },
        {
            "task": "extract_pnl_summary",
            "description": "Extract P&L summary: revenue, COGS, opex, net income, period",
            "schema": {"revenue": "", "cogs": "", "gross_margin": "", "opex": "", "net_income": "", "period": ""},
        },
        {
            "task": "extract_runway",
            "description": "Extract runway: cash on hand, monthly burn, runway months, last raise date/amount",
            "schema": {"cash": "", "monthly_burn": "", "runway_months": "", "last_raise": ""},
        },
    ],
    "legal": [
        {
            "task": "extract_parties",
            "description": "Extract contract parties, effective date, governing law, term",
            "schema": {"parties": [], "effective_date": "", "governing_law": "", "term": ""},
        },
        {
            "task": "extract_key_terms",
            "description": "Extract key contract terms: termination, liability cap, IP assignment, non-compete",
            "schema": {"termination": "", "liability_cap": "", "ip_assignment": "", "non_compete": "", "indemnification": ""},
        },
    ],
    "commercial": [
        {
            "task": "extract_customer_list",
            "description": "Extract customer names, contract values, start dates, status",
            "schema": {"customers": [], "contract_values": [], "dates": [], "status": []},
        },
        {
            "task": "extract_gtm_metrics",
            "description": "Extract GTM metrics: CAC, LTV, payback period, channels, conversion rates",
            "schema": {"cac": "", "ltv": "", "payback_months": "", "channels": [], "conversion_rate": ""},
        },
    ],
    "product_technical": [
        {
            "task": "extract_tech_stack",
            "description": "Extract tech stack: languages, frameworks, infrastructure, databases, services",
            "schema": {"languages": [], "frameworks": [], "infrastructure": [], "databases": [], "services": []},
        },
        {
            "task": "extract_roadmap",
            "description": "Extract product roadmap: items, timeline, status, resource needs",
            "schema": {"items": [], "timeline": "", "status": [], "resource_needs": []},
        },
    ],
}


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


# ── Subcommand: info ────────────────────────────────────────────────────

def cmd_info(args):
    """Return document metadata: page count, char stats, TOC, extraction methods."""
    conn = get_db()
    rows = conn.execute(
        """SELECT page_number, char_count, extraction_method, extraction_quality, metadata
           FROM document_pages
           WHERE file_path = ? AND dataroom_slug = ?
           ORDER BY page_number""",
        (args.file, args.dataroom),
    ).fetchall()

    if not rows:
        print(json.dumps({"error": f"No pages found for {args.file} in {args.dataroom}"}))
        conn.close()
        return

    page_stats = []
    for r in rows:
        meta = json.loads(r["metadata"]) if r["metadata"] else {}
        label = meta.get("sheet_name") or meta.get("slide_title") or f"Page {r['page_number']}"
        page_stats.append({
            "page": r["page_number"],
            "chars": r["char_count"],
            "method": r["extraction_method"],
            "quality": r["extraction_quality"],
            "label": label,
        })

    methods = list(set(p["method"] for p in page_stats))
    total_chars = sum(p["chars"] for p in page_stats)

    print(json.dumps({
        "file_path": args.file,
        "dataroom": args.dataroom,
        "page_count": len(rows),
        "total_chars": total_chars,
        "extraction_methods": methods,
        "pages": page_stats,
    }, indent=2))
    conn.close()


# ── Subcommand: slice ───────────────────────────────────────────────────

def cmd_slice(args):
    """Return text content for a page range."""
    conn = get_db()

    # Parse page range
    if "-" in args.pages:
        start, end = args.pages.split("-")
        start, end = int(start), int(end)
    else:
        start = end = int(args.pages)

    rows = conn.execute(
        """SELECT page_number, text_content FROM document_pages
           WHERE file_path = ? AND dataroom_slug = ?
           AND page_number >= ? AND page_number <= ?
           ORDER BY page_number""",
        (args.file, args.dataroom, start, end),
    ).fetchall()

    for r in rows:
        print(f"--- Page {r['page_number']} ---")
        print(r["text_content"] or "(empty)")
        print()

    conn.close()


# ── Subcommand: search ──────────────────────────────────────────────────

def cmd_search(args):
    """Search document pages for a query string."""
    conn = get_db()
    rows = conn.execute(
        """SELECT page_number, text_content FROM document_pages
           WHERE file_path = ? AND dataroom_slug = ?
           AND text_content LIKE ?
           ORDER BY page_number""",
        (args.file, args.dataroom, f"%{args.query}%"),
    ).fetchall()

    results = []
    max_results = args.max_results or 10
    for r in rows[:max_results]:
        text = r["text_content"] or ""
        idx = text.lower().find(args.query.lower())
        if idx >= 0:
            start = max(0, idx - 100)
            end = min(len(text), idx + len(args.query) + 100)
            snippet = text[start:end].strip()
        else:
            snippet = text[:200].strip()
        results.append({"page": r["page_number"], "snippet": snippet})

    print(json.dumps({
        "query": args.query,
        "total_matches": len(rows),
        "results": results,
    }, indent=2))
    conn.close()


# ── Subcommand: tasks ───────────────────────────────────────────────────

def cmd_tasks(args):
    """List predefined extraction tasks for a category."""
    if args.category:
        tasks = EXTRACTION_TASKS.get(args.category, [])
        print(json.dumps({
            "category": args.category,
            "tasks": tasks,
        }, indent=2))
    else:
        # List all categories
        summary = {cat: [t["task"] for t in tasks] for cat, tasks in EXTRACTION_TASKS.items()}
        print(json.dumps(summary, indent=2))


# ── Subcommand: store ───────────────────────────────────────────────────

def cmd_store(args):
    """Store a structured extraction result in document_extractions."""
    conn = get_db()

    # Validate JSON
    try:
        content = json.loads(args.content)
        content_str = json.dumps(content)
    except json.JSONDecodeError:
        content_str = args.content

    cursor = conn.execute(
        """INSERT INTO document_extractions
           (file_path, dataroom_slug, extraction_type, extraction_key, content,
            page_range, confidence, model_used)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            args.file,
            args.dataroom,
            args.type or "extraction",
            args.key,
            content_str,
            args.page_range,
            args.confidence or 1.0,
            "claude-code",
        ),
    )
    conn.commit()

    print(json.dumps({
        "status": "stored",
        "extraction_id": cursor.lastrowid,
        "file": args.file,
        "dataroom": args.dataroom,
        "key": args.key,
    }, indent=2))
    conn.close()


# ── Subcommand: list-files ──────────────────────────────────────────────

def cmd_list_files(args):
    """List all extracted files in a dataroom."""
    conn = get_db()
    rows = conn.execute(
        """SELECT file_path, COUNT(*) as pages, SUM(char_count) as total_chars,
                  GROUP_CONCAT(DISTINCT extraction_method) as methods
           FROM document_pages
           WHERE dataroom_slug = ?
           GROUP BY file_path
           ORDER BY file_path""",
        (args.dataroom,),
    ).fetchall()

    files = []
    for r in rows:
        files.append({
            "file_path": r["file_path"],
            "pages": r["pages"],
            "total_chars": r["total_chars"],
            "methods": r["methods"],
        })

    print(json.dumps({
        "dataroom": args.dataroom,
        "file_count": len(files),
        "files": files,
    }, indent=2))
    conn.close()


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="VFT RLM Document Access CLI — used by Claude Code for document processing",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # info
    p_info = subparsers.add_parser("info", help="Get document metadata and page stats")
    p_info.add_argument("--file", required=True, help="File path in dataroom")
    p_info.add_argument("--dataroom", required=True, help="Dataroom slug")

    # slice
    p_slice = subparsers.add_parser("slice", help="Get text for a page range")
    p_slice.add_argument("--file", required=True)
    p_slice.add_argument("--dataroom", required=True)
    p_slice.add_argument("--pages", required=True, help="Page range: '1-3' or '5'")

    # search
    p_search = subparsers.add_parser("search", help="Search pages for a query")
    p_search.add_argument("--file", required=True)
    p_search.add_argument("--dataroom", required=True)
    p_search.add_argument("--query", required=True, help="Search query")
    p_search.add_argument("--max-results", type=int, default=10)

    # tasks
    p_tasks = subparsers.add_parser("tasks", help="List predefined extraction tasks")
    p_tasks.add_argument("--category", help="Document category (governance, finance, legal, commercial, product_technical)")

    # store
    p_store = subparsers.add_parser("store", help="Store an extraction result")
    p_store.add_argument("--file", required=True)
    p_store.add_argument("--dataroom", required=True)
    p_store.add_argument("--key", required=True, help="Extraction key (e.g. safe_terms, revenue_metrics)")
    p_store.add_argument("--content", required=True, help="JSON extraction result")
    p_store.add_argument("--type", default="extraction", help="Extraction type")
    p_store.add_argument("--page-range", help="Source page range")
    p_store.add_argument("--confidence", type=float, default=1.0)

    # list-files
    p_list = subparsers.add_parser("list-files", help="List all extracted files in a dataroom")
    p_list.add_argument("--dataroom", required=True)

    args = parser.parse_args()

    commands = {
        "info": cmd_info,
        "slice": cmd_slice,
        "search": cmd_search,
        "tasks": cmd_tasks,
        "store": cmd_store,
        "list-files": cmd_list_files,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
