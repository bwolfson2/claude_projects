---
name: sheet-sync
description: Sync fund data (deals, projects, contacts) to a Google Sheets dashboard via the gspread API. Creates and maintains tabs for DD Pipeline, Projects, CRM Contacts, and per-deal/per-project detail sheets. Use when the user wants to push data to Google Sheets, create the dashboard, or update specific tabs.
---

# Sheet Sync

Push local fund data to a shared Google Sheets dashboard on Google Drive. Uses `gspread` (Google Sheets API via service account) for headless, reliable sync.

## Prerequisites

1. **Google Cloud service account** with Sheets API enabled
2. Service account JSON key at `~/.config/gspread/service_account.json`
3. Google Sheet shared with the service account email (editor access)
4. `pip install gspread google-auth`

## Sheet Structure

| Tab | Content |
|-----|---------|
| DD Pipeline | All deals — one row per company with stage, status, diligence progress, docs, links |
| Projects | All projects by type with status, owner, links |
| CRM Contacts | All contacts across platforms with handles and relationship context |
| DD: {Company} | Per-deal detail tab — diligence tracks, recent activity, findings, actions |
| Proj: {Project} | Per-project detail tab — status, milestones, activity, assets |

## Scripts

### Initialize the Google Sheet
```bash
python skills/sheet-sync/scripts/create_sheet.py
```
Creates the sheet with all tabs, headers, column widths, and conditional formatting. Safe to re-run (skips existing tabs).

### Push data to sheets
```bash
python skills/sheet-sync/scripts/sync_to_sheets.py
```
Reads `deals.json`, `projects.json`, `contacts.json` and writes to respective tabs. Overwrites data rows, preserves headers.

### Update detail tabs
```bash
python skills/sheet-sync/scripts/update_detail_tabs.py
```
Creates/updates per-deal "DD: {Company}" and per-project "Proj: {Project}" tabs with summary data.

## Data Flow

```
deals.json ──┐
projects.json ├─→ sync_to_sheets.py ──→ Google Sheets (shared dashboard)
contacts.json ┘
```

## Configuration

Set the sheet ID via environment variable or config:
```bash
export VFT_SHEET_ID="your-google-sheet-id-here"
```

Or store in `fund/metadata/config.json`:
```json
{
  "google_sheet_id": "your-google-sheet-id-here"
}
```
