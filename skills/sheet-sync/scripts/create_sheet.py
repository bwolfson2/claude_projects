#!/usr/bin/env python3
"""Create and initialize the Google Sheets dashboard.

Sets up tabs, headers, column widths, and conditional formatting.
Safe to re-run — skips tabs that already exist.

Usage:
    python create_sheet.py                       # Create using VFT_SHEET_ID env var
    python create_sheet.py --sheet-id <ID>       # Explicit sheet ID
    python create_sheet.py --create "Fund Dashboard"  # Create a new sheet
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import gspread
    from gspread.utils import rowcol_to_a1
except ImportError:
    print("Missing dependency: pip install gspread google-auth", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(os.environ.get("VFT_REPO_ROOT",
    Path(__file__).resolve().parents[3]))
CONFIG_PATH = REPO_ROOT / "fund" / "metadata" / "config.json"

# Column definitions for each tab
DD_PIPELINE_HEADERS = [
    "Company", "Stage", "Status", "Priority", "Sector", "Round",
    "Raise ($)", "Val Cap ($)", "Decision", "Owner", "Last Touch",
    "Next Action", "Due Date", "Docs Uploaded", "Dataroom Link",
    "Commercial DD", "Product/Tech DD", "Finance/Legal DD", "Memo DD",
    "Memo Link", "Terms", "Thesis", "Comments"
]

PROJECTS_HEADERS = [
    "Name", "Type", "Category", "Status", "Priority", "Owner",
    "Created", "Last Updated", "Description", "Next Action"
]

CRM_HEADERS = [
    "Name", "Email", "Company", "Role/Title", "Phone",
    "Slack", "WhatsApp", "Signal", "LinkedIn", "Tags",
    "Last Contacted", "Source", "Context", "Related Deals", "Related Projects"
]


def get_sheet_id(args_sheet_id: str = None) -> str:
    """Resolve Google Sheet ID from args, env, or config."""
    if args_sheet_id:
        return args_sheet_id
    if os.environ.get("VFT_SHEET_ID"):
        return os.environ["VFT_SHEET_ID"]
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text())
        if config.get("google_sheet_id"):
            return config["google_sheet_id"]
    return ""


def get_gc() -> gspread.Client:
    """Authenticate with Google Sheets API."""
    sa_path = Path.home() / ".config" / "gspread" / "service_account.json"
    if sa_path.exists():
        return gspread.service_account(filename=str(sa_path))
    # Fall back to default credentials
    return gspread.service_account()


def ensure_tab(sh: gspread.Spreadsheet, title: str, headers: list[str],
               col_widths: dict[int, int] = None) -> gspread.Worksheet:
    """Create a worksheet tab if it doesn't exist, set headers."""
    try:
        ws = sh.worksheet(title)
        print(f"  Tab '{title}' already exists — skipping creation")
        return ws
    except gspread.WorksheetNotFound:
        pass

    ws = sh.add_worksheet(title=title, rows=1000, cols=len(headers))
    ws.update([headers], "A1")

    # Bold header row
    ws.format("1:1", {
        "textFormat": {"bold": True},
        "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.95}
    })

    # Freeze header row
    ws.freeze(rows=1)

    # Set column widths
    if col_widths:
        requests = []
        for col_idx, width in col_widths.items():
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": ws.id,
                        "dimension": "COLUMNS",
                        "startIndex": col_idx,
                        "endIndex": col_idx + 1
                    },
                    "properties": {"pixelSize": width},
                    "fields": "pixelSize"
                }
            })
        if requests:
            sh.batch_update({"requests": requests})

    print(f"  Created tab '{title}' with {len(headers)} columns")
    return ws


def create_dashboard(sheet_id: str = None, create_title: str = None):
    """Create or initialize the Google Sheets dashboard."""
    gc = get_gc()

    if create_title:
        sh = gc.create(create_title)
        sheet_id = sh.id
        print(f"Created new sheet: '{create_title}'")
        print(f"  Sheet ID: {sheet_id}")
        print(f"  URL: {sh.url}")

        # Save to config
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        config = {}
        if CONFIG_PATH.exists():
            config = json.loads(CONFIG_PATH.read_text())
        config["google_sheet_id"] = sheet_id
        CONFIG_PATH.write_text(json.dumps(config, indent=2))
        print(f"  Saved sheet ID to {CONFIG_PATH}")
    else:
        if not sheet_id:
            print("No sheet ID provided. Use --sheet-id, VFT_SHEET_ID env var, "
                  "or --create to make a new sheet.", file=sys.stderr)
            sys.exit(1)
        sh = gc.open_by_key(sheet_id)
        print(f"Opened sheet: '{sh.title}'")

    # Create main tabs
    print("\nSetting up tabs...")

    dd_widths = {0: 180, 1: 100, 2: 80, 3: 80, 4: 120, 5: 80,
                 6: 120, 7: 120, 8: 120, 9: 100, 10: 110,
                 11: 200, 12: 110, 13: 60, 14: 200,
                 15: 100, 16: 100, 17: 100, 18: 100,
                 19: 200, 20: 200, 21: 250, 22: 250}
    ensure_tab(sh, "DD Pipeline", DD_PIPELINE_HEADERS, dd_widths)

    proj_widths = {0: 200, 1: 120, 2: 120, 3: 100, 4: 80, 5: 100,
                   6: 110, 7: 110, 8: 300, 9: 200}
    ensure_tab(sh, "Projects", PROJECTS_HEADERS, proj_widths)

    crm_widths = {0: 180, 1: 220, 2: 150, 3: 150, 4: 140,
                  5: 120, 6: 140, 7: 140, 8: 250, 9: 200,
                  10: 120, 11: 100, 12: 300, 13: 200, 14: 200}
    ensure_tab(sh, "CRM Contacts", CRM_HEADERS, crm_widths)

    # Remove default "Sheet1" if it exists and we created new tabs
    try:
        default_ws = sh.worksheet("Sheet1")
        if len(sh.worksheets()) > 1:
            sh.del_worksheet(default_ws)
            print("  Removed default 'Sheet1' tab")
    except gspread.WorksheetNotFound:
        pass

    print(f"\nDashboard ready: {sh.url}")
    return sh


def main():
    parser = argparse.ArgumentParser(description="Create Google Sheets dashboard")
    parser.add_argument("--sheet-id", type=str, help="Google Sheet ID")
    parser.add_argument("--create", type=str, metavar="TITLE",
                        help="Create a new sheet with this title")
    args = parser.parse_args()

    sheet_id = get_sheet_id(args.sheet_id)
    create_dashboard(sheet_id=sheet_id, create_title=args.create)


if __name__ == "__main__":
    main()
