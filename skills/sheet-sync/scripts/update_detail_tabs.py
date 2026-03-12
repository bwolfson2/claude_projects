#!/usr/bin/env python3
"""Create and update per-deal and per-project detail tabs.

For each active deal, creates a "DD: {Company}" tab with diligence summary.
For each active project, creates a "Proj: {Project}" tab with status summary.

Usage:
    python update_detail_tabs.py                 # Update all detail tabs
    python update_detail_tabs.py --deals-only    # Only deal tabs
    python update_detail_tabs.py --projects-only # Only project tabs
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

try:
    import gspread
except ImportError:
    print("Missing dependency: pip install gspread google-auth", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(os.environ.get("VFT_REPO_ROOT",
    Path(__file__).resolve().parents[3]))
CONFIG_PATH = REPO_ROOT / "fund" / "metadata" / "config.json"
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"

DEALS_JSON = REPO_ROOT / "fund" / "deals.json"
PROJECTS_JSON = REPO_ROOT / "fund" / "projects.json"
CONTACTS_JSON = REPO_ROOT / "fund" / "crm" / "contacts.json"

DD_STATUS_MAP = {
    "complete": "Done",
    "in_progress": "In Progress",
    "pending": "Pending",
    "not_started": "Not Started",
    "blocked": "Blocked",
}


def get_sheet_id() -> str:
    if os.environ.get("VFT_SHEET_ID"):
        return os.environ["VFT_SHEET_ID"]
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text())
        if config.get("google_sheet_id"):
            return config["google_sheet_id"]
    print("No sheet ID found.", file=sys.stderr)
    sys.exit(1)


def get_gc() -> gspread.Client:
    sa_path = Path.home() / ".config" / "gspread" / "service_account.json"
    if sa_path.exists():
        return gspread.service_account(filename=str(sa_path))
    return gspread.service_account()


def safe_get(d: dict, *keys, default=""):
    current = d
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current if current is not None else default


def get_recent_messages(slug: str, limit: int = 10) -> list[dict]:
    """Get recent messages related to a deal/project slug."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT timestamp, source, sender, subject, snippet
        FROM messages
        WHERE project_tags LIKE ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (f'%"{slug}"%', limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_contacts_for(slugs: list[str], slug_field: str = "deal_slugs") -> list[dict]:
    """Get contacts linked to deal or project slugs."""
    if not CONTACTS_JSON.exists():
        return []
    contacts = json.loads(CONTACTS_JSON.read_text())
    matched = []
    for c in contacts:
        linked = c.get(slug_field, [])
        if isinstance(linked, str):
            try:
                linked = json.loads(linked)
            except (json.JSONDecodeError, TypeError):
                linked = []
        if any(s in linked for s in slugs):
            matched.append(c)
    return matched


def ensure_detail_tab(sh: gspread.Spreadsheet, title: str, rows: list[list]) -> gspread.Worksheet:
    """Create or update a detail tab with the given rows."""
    # Sanitize title (max 100 chars for sheet tab names)
    title = title[:100]

    try:
        ws = sh.worksheet(title)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=max(len(rows) + 10, 50), cols=8)

    if rows:
        ws.update(rows, "A1")

    return ws


def build_deal_tab(deal: dict) -> list[list]:
    """Build rows for a per-deal detail tab."""
    rows = []
    diligence = deal.get("diligence", {})
    artifacts = deal.get("artifacts", {})
    slug = deal.get("slug", "")

    # Header block
    rows.append(["Company", safe_get(deal, "company_name")])
    rows.append(["Stage", safe_get(deal, "stage")])
    rows.append(["Status", safe_get(deal, "status")])
    rows.append(["Round", safe_get(deal, "round")])
    rows.append(["Raise", safe_get(deal, "raise_usd")])
    rows.append(["Valuation Cap", safe_get(deal, "valuation_cap_usd")])
    rows.append(["Decision", safe_get(deal, "decision_posture")])
    rows.append(["Owner", safe_get(deal, "owner")])
    rows.append(["Last Touch", safe_get(deal, "last_touch")])
    rows.append(["Next Action", safe_get(deal, "next_action")])
    rows.append(["Due Date", safe_get(deal, "next_action_due")])
    rows.append([])

    # Diligence progress
    rows.append(["DILIGENCE PROGRESS", "Status", "Notes"])
    tracks = [
        ("Commercial", "commercial"),
        ("Product/Technical", "product_technical"),
        ("Finance/Legal", "finance_legal"),
        ("Memo", "memo"),
    ]
    for label, key in tracks:
        status = DD_STATUS_MAP.get(safe_get(diligence, key), "—")
        notes = safe_get(diligence, f"{key}_notes")
        rows.append([label, status, notes])
    rows.append([])

    # Thesis
    thesis = safe_get(deal, "thesis")
    if thesis:
        rows.append(["THESIS"])
        rows.append([thesis])
        rows.append([])

    # Terms
    terms = safe_get(deal, "terms_summary")
    if terms:
        rows.append(["TERMS"])
        rows.append([terms])
        rows.append([])

    # Artifacts
    rows.append(["ARTIFACTS"])
    if safe_get(artifacts, "dataroom"):
        rows.append(["Dataroom", artifacts["dataroom"]])
    if safe_get(artifacts, "short_memo"):
        rows.append(["Memo", artifacts["short_memo"]])
    if safe_get(artifacts, "deck"):
        rows.append(["Deck", artifacts["deck"]])
    rows.append([])

    # Recent activity
    messages = get_recent_messages(slug)
    if messages:
        rows.append(["RECENT ACTIVITY", "Source", "From", "Subject"])
        for m in messages:
            rows.append([
                m.get("timestamp", "")[:10],
                m.get("source", ""),
                m.get("sender", ""),
                (m.get("subject") or m.get("snippet") or "")[:80],
            ])
        rows.append([])

    # Open questions
    questions = deal.get("open_questions", [])
    if questions:
        rows.append(["OPEN QUESTIONS"])
        for q in questions:
            rows.append([f"  - {q}"])
        rows.append([])

    # Contacts
    contacts = get_contacts_for([slug], "deal_slugs")
    if contacts:
        rows.append(["CONTACTS", "Email", "Company", "Title"])
        for c in contacts:
            rows.append([
                c.get("name", ""),
                c.get("email", ""),
                c.get("company", ""),
                c.get("title", ""),
            ])

    return rows


def build_project_tab(project: dict) -> list[list]:
    """Build rows for a per-project detail tab."""
    rows = []
    slug = project.get("slug", "")

    # Header block
    rows.append(["Project", safe_get(project, "project_name")])
    rows.append(["Type", safe_get(project, "project_type")])
    rows.append(["Category", safe_get(project, "category")])
    rows.append(["Status", safe_get(project, "status")])
    rows.append(["Priority", safe_get(project, "priority")])
    rows.append(["Owner", safe_get(project, "owner")])
    rows.append(["Created", safe_get(project, "created")])
    rows.append(["Last Updated", safe_get(project, "last_updated")])
    rows.append([])

    # Description
    desc = safe_get(project, "description")
    if desc:
        rows.append(["DESCRIPTION"])
        rows.append([desc])
        rows.append([])

    # Recent activity
    messages = get_recent_messages(slug)
    if messages:
        rows.append(["RECENT ACTIVITY", "Source", "From", "Subject"])
        for m in messages:
            rows.append([
                m.get("timestamp", "")[:10],
                m.get("source", ""),
                m.get("sender", ""),
                (m.get("subject") or m.get("snippet") or "")[:80],
            ])
        rows.append([])

    # Action items
    actions = project.get("action_items", [])
    if actions:
        rows.append(["ACTION ITEMS"])
        for a in actions:
            if isinstance(a, dict):
                rows.append([f"  - {a.get('action', a)}", a.get("owner", ""), a.get("due", "")])
            else:
                rows.append([f"  - {a}"])
        rows.append([])

    # Contacts
    contacts = get_contacts_for([slug], "project_slugs")
    if contacts:
        rows.append(["CONTACTS", "Email", "Company", "Title"])
        for c in contacts:
            rows.append([
                c.get("name", ""),
                c.get("email", ""),
                c.get("company", ""),
                c.get("title", ""),
            ])

    return rows


def update_deal_tabs(sh: gspread.Spreadsheet):
    """Create/update per-deal detail tabs."""
    if not DEALS_JSON.exists():
        print("  deals.json not found — skipping deal tabs")
        return 0

    deals = json.loads(DEALS_JSON.read_text())
    count = 0

    for deal in deals:
        status = deal.get("status", "active")
        if status == "passed":
            continue  # Skip passed deals

        company = deal.get("company_name", "Unknown")
        tab_title = f"DD: {company}"
        tab_rows = build_deal_tab(deal)
        ensure_detail_tab(sh, tab_title, tab_rows)
        count += 1
        print(f"  Updated tab '{tab_title}'")

    return count


def update_project_tabs(sh: gspread.Spreadsheet):
    """Create/update per-project detail tabs."""
    if not PROJECTS_JSON.exists():
        print("  projects.json not found — skipping project tabs")
        return 0

    projects = json.loads(PROJECTS_JSON.read_text())
    count = 0

    for project in projects:
        status = project.get("status", "active")
        if status in ("archived", "cancelled"):
            continue

        name = project.get("project_name", "Unknown")
        tab_title = f"Proj: {name}"
        tab_rows = build_project_tab(project)
        ensure_detail_tab(sh, tab_title, tab_rows)
        count += 1
        print(f"  Updated tab '{tab_title}'")

    return count


def main():
    parser = argparse.ArgumentParser(description="Update per-deal and per-project detail tabs")
    parser.add_argument("--deals-only", action="store_true")
    parser.add_argument("--projects-only", action="store_true")
    args = parser.parse_args()

    sheet_id = get_sheet_id()
    gc = get_gc()
    sh = gc.open_by_key(sheet_id)
    print(f"Updating detail tabs in: '{sh.title}'")

    if not args.projects_only:
        deal_count = update_deal_tabs(sh)
        print(f"  {deal_count} deal tabs updated")

    if not args.deals_only:
        proj_count = update_project_tabs(sh)
        print(f"  {proj_count} project tabs updated")

    print(f"\nDone. Sheet URL: {sh.url}")


if __name__ == "__main__":
    main()
