---
description: Push deals, projects, and contacts to the Google Sheets dashboard
argument-hint: "[setup|deals|projects|contacts]"
---

# Sync Sheet

Push current fund data to the shared Google Sheets dashboard.

## Arguments

`$ARGUMENTS`

- **No argument** — Sync all tabs (DD Pipeline, Projects, CRM Contacts) + update detail tabs
- **`setup`** — Create the Google Sheet and initialize all tabs
- **`deals`** — Sync only the DD Pipeline tab
- **`projects`** — Sync only the Projects tab
- **`contacts`** — Sync only the CRM Contacts tab

## Steps

### If `setup`:
1. Run `python skills/sheet-sync/scripts/create_sheet.py --create "VFT Fund Dashboard"`
2. Print the sheet URL and instruct the user to:
   - Share the sheet with team members
   - Note the sheet ID is saved to `fund/metadata/config.json`

### If specific tab:
1. Run `python skills/sheet-sync/scripts/sync_to_sheets.py --tab <tab_name>`
2. Report number of rows synced

### If no argument (full sync):
1. First, export latest contacts from DB:
   ```bash
   python skills/crm-contacts/scripts/sync_contacts.py
   ```
2. Sync all data to sheets:
   ```bash
   python skills/sheet-sync/scripts/sync_to_sheets.py
   ```
3. Update per-deal and per-project detail tabs:
   ```bash
   python skills/sheet-sync/scripts/update_detail_tabs.py
   ```
4. Report summary: deals synced, projects synced, contacts synced, detail tabs created/updated
5. Print the sheet URL

## Prerequisites

- Google service account key at `~/.config/gspread/service_account.json`
- Sheet ID in `VFT_SHEET_ID` env var or `fund/metadata/config.json`
- `pip install gspread google-auth`

If prerequisites are missing, guide the user through setup:
1. Create a Google Cloud project and enable the Sheets API
2. Create a service account, download the JSON key
3. Place it at `~/.config/gspread/service_account.json`
4. Run `/vft-fund-tools:sync-sheet setup` to create the sheet
