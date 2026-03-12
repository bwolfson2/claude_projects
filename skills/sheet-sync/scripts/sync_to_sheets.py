#!/usr/bin/env python3
"""Sync local JSON data to Google Sheets dashboard.

Reads deals.json, projects.json, contacts.json and writes to respective tabs.
Overwrites data rows, preserves headers.

Usage:
    python sync_to_sheets.py                    # Sync all tabs
    python sync_to_sheets.py --tab deals        # Sync only deals
    python sync_to_sheets.py --tab projects     # Sync only projects
    python sync_to_sheets.py --tab contacts     # Sync only contacts
"""

import argparse
import json
import os
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

DEALS_JSON = REPO_ROOT / "fund" / "deals.json"
PROJECTS_JSON = REPO_ROOT / "fund" / "projects.json"
CONTACTS_JSON = REPO_ROOT / "fund" / "crm" / "contacts.json"

# Diligence status display mapping
DD_STATUS_MAP = {
    "complete": "Done",
    "in_progress": "In Progress",
    "pending": "Pending",
    "not_started": "Not Started",
    "blocked": "Blocked",
    "": "—",
    None: "—",
}


def get_sheet_id() -> str:
    if os.environ.get("VFT_SHEET_ID"):
        return os.environ["VFT_SHEET_ID"]
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text())
        if config.get("google_sheet_id"):
            return config["google_sheet_id"]
    print("No sheet ID found. Set VFT_SHEET_ID or run create_sheet.py first.",
          file=sys.stderr)
    sys.exit(1)


def get_gc() -> gspread.Client:
    sa_path = Path.home() / ".config" / "gspread" / "service_account.json"
    if sa_path.exists():
        return gspread.service_account(filename=str(sa_path))
    return gspread.service_account()


def safe_get(d: dict, *keys, default=""):
    """Safely traverse nested dict keys."""
    current = d
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current if current is not None else default


def truncate(text: str, max_len: int = 200) -> str:
    if not text:
        return ""
    text = str(text)
    return text[:max_len] + "..." if len(text) > max_len else text


def list_to_str(val) -> str:
    """Convert a JSON array (or already-parsed list) to comma-separated string."""
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val) if val else ""


def sync_deals(sh: gspread.Spreadsheet):
    """Sync deals.json to the DD Pipeline tab."""
    if not DEALS_JSON.exists():
        print("  deals.json not found — skipping")
        return 0

    deals = json.loads(DEALS_JSON.read_text())
    if not deals:
        print("  No deals to sync")
        return 0

    try:
        ws = sh.worksheet("DD Pipeline")
    except gspread.WorksheetNotFound:
        print("  DD Pipeline tab not found — run create_sheet.py first")
        return 0

    rows = []
    for d in deals:
        diligence = d.get("diligence", {})
        artifacts = d.get("artifacts", {})
        doc_pages = d.get("document_pages", [])

        row = [
            safe_get(d, "company_name"),
            safe_get(d, "stage"),
            safe_get(d, "status"),
            safe_get(d, "priority"),
            safe_get(d, "sector"),
            safe_get(d, "round"),
            safe_get(d, "raise_usd"),
            safe_get(d, "valuation_cap_usd"),
            safe_get(d, "decision_posture"),
            safe_get(d, "owner"),
            safe_get(d, "last_touch"),
            safe_get(d, "next_action"),
            safe_get(d, "next_action_due"),
            len(doc_pages) if isinstance(doc_pages, list) else 0,
            safe_get(artifacts, "dataroom"),
            DD_STATUS_MAP.get(safe_get(diligence, "commercial"), "—"),
            DD_STATUS_MAP.get(safe_get(diligence, "product_technical"), "—"),
            DD_STATUS_MAP.get(safe_get(diligence, "finance_legal"), "—"),
            DD_STATUS_MAP.get(safe_get(diligence, "memo"), "—"),
            safe_get(artifacts, "short_memo"),
            safe_get(d, "terms_summary"),
            truncate(safe_get(d, "thesis")),
            safe_get(d, "comments"),
        ]
        rows.append(row)

    # Clear existing data (rows 2+) and write new data
    if rows:
        ws.batch_clear([f"A2:W{len(rows) + 1000}"])
        ws.update(rows, f"A2")

    print(f"  Synced {len(rows)} deals to DD Pipeline")
    return len(rows)


def sync_projects(sh: gspread.Spreadsheet):
    """Sync projects.json to the Projects tab."""
    if not PROJECTS_JSON.exists():
        print("  projects.json not found — skipping")
        return 0

    projects = json.loads(PROJECTS_JSON.read_text())
    if not projects:
        print("  No projects to sync")
        return 0

    try:
        ws = sh.worksheet("Projects")
    except gspread.WorksheetNotFound:
        print("  Projects tab not found — run create_sheet.py first")
        return 0

    rows = []
    for p in projects:
        row = [
            safe_get(p, "project_name"),
            safe_get(p, "project_type"),
            safe_get(p, "category"),
            safe_get(p, "status"),
            safe_get(p, "priority"),
            safe_get(p, "owner"),
            safe_get(p, "created"),
            safe_get(p, "last_updated"),
            truncate(safe_get(p, "description")),
            safe_get(p, "next_action"),
        ]
        rows.append(row)

    if rows:
        ws.batch_clear([f"A2:J{len(rows) + 1000}"])
        ws.update(rows, f"A2")

    print(f"  Synced {len(rows)} projects to Projects tab")
    return len(rows)


def sync_contacts(sh: gspread.Spreadsheet):
    """Sync contacts.json to the CRM Contacts tab."""
    if not CONTACTS_JSON.exists():
        print("  contacts.json not found — skipping")
        return 0

    contacts = json.loads(CONTACTS_JSON.read_text())
    if not contacts:
        print("  No contacts to sync")
        return 0

    try:
        ws = sh.worksheet("CRM Contacts")
    except gspread.WorksheetNotFound:
        print("  CRM Contacts tab not found — run create_sheet.py first")
        return 0

    rows = []
    for c in contacts:
        row = [
            safe_get(c, "name"),
            safe_get(c, "email"),
            safe_get(c, "company"),
            safe_get(c, "title"),
            safe_get(c, "phone"),
            safe_get(c, "slack_handle"),
            safe_get(c, "whatsapp_id"),
            safe_get(c, "signal_id"),
            safe_get(c, "linkedin_url"),
            list_to_str(c.get("tags", [])),
            safe_get(c, "last_contacted"),
            safe_get(c, "source"),
            truncate(safe_get(c, "context"), 300),
            list_to_str(c.get("deal_slugs", [])),
            list_to_str(c.get("project_slugs", [])),
        ]
        rows.append(row)

    if rows:
        ws.batch_clear([f"A2:O{len(rows) + 1000}"])
        ws.update(rows, f"A2")

    print(f"  Synced {len(rows)} contacts to CRM Contacts tab")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Sync JSON data to Google Sheets")
    parser.add_argument("--tab", choices=["deals", "projects", "contacts"],
                        help="Sync only a specific tab")
    args = parser.parse_args()

    sheet_id = get_sheet_id()
    gc = get_gc()
    sh = gc.open_by_key(sheet_id)
    print(f"Syncing to sheet: '{sh.title}'")

    totals = {}
    if not args.tab or args.tab == "deals":
        totals["deals"] = sync_deals(sh)
    if not args.tab or args.tab == "projects":
        totals["projects"] = sync_projects(sh)
    if not args.tab or args.tab == "contacts":
        totals["contacts"] = sync_contacts(sh)

    print(f"\nSync complete: {json.dumps(totals)}")
    print(f"Sheet URL: {sh.url}")


if __name__ == "__main__":
    main()
