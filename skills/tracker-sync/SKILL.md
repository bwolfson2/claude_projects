---
name: tracker-sync
description: Sync local JSON data (deals.json and projects.json) to the master Excel spreadsheet (VFT-Master-Tracker.xlsx). This is the integration layer between the CRM data and the spreadsheet, maintaining a single source of truth across JSON and Excel formats.
---

# Tracker Sync Skill

Maintain synchronization between the fund's local JSON CRM data and the master Excel spreadsheet. This skill provides bidirectional sync capabilities, allowing data to flow from the CRM into Excel for reporting and optionally back from Google Sheets edits into JSON.

## Core Purpose

The tracker-sync skill serves as the integration layer between:
- **Source of Truth**: `/fund/crm/deals.json` and `/projects/projects.json` (local JSON, version-controlled)
- **Reporting/Collaboration Format**: `/fund/VFT-Master-Tracker.xlsx` (Excel workbook)

This ensures:
- Deal pipeline status is always current in the spreadsheet
- Project management data stays in sync
- Formatting and structure are preserved
- Changes are logged for audit purposes

## When to Use This Skill

### Sync to Excel (`scripts/sync_to_xlsx.py`)
Use this **before sharing the spreadsheet** or **after updating JSON records**:
- After running `upsert_deal` to update a company in the CRM
- After creating or updating project records
- Before sharing the tracker with stakeholders
- As part of a daily/weekly refresh routine
- When the spreadsheet is opened read-only (ensure JSON is source of truth)

### Sync from Excel (`scripts/sync_from_xlsx.py`)
Use this **when edits are made directly in Google Sheets**:
- After multiple team members edit the spreadsheet in Google Sheets
- To pull manual corrections back into the JSON CRM
- When the spreadsheet is shared for collaborative editing
- Only if teams prefer editing in Sheets over JSON directly

**Recommendation**: Keep JSON as source of truth. Use Excel as a reporting artifact that gets refreshed, not as a collaborative editing interface.

## Data Flows

### JSON → Excel (Primary Direction)

```
deals.json
  ├── Extract company records
  ├── Map fields to DD Pipeline columns
  └── Write to VFT-Master-Tracker.xlsx [DD Pipeline tab]

projects.json (if exists)
  ├── Extract project records
  ├── Map fields to Project Management columns
  └── Write to VFT-Master-Tracker.xlsx [Project Management tab]
```

### Excel → JSON (Reverse Sync - Optional)

```
VFT-Master-Tracker.xlsx
  ├── Read DD Pipeline tab
  ├── Compare against deals.json
  ├── Write changed records back to deals.json
  └── Log what was updated

VFT-Master-Tracker.xlsx
  ├── Read Project Management tab
  ├── Compare against projects.json
  ├── Write changed records back to projects.json
  └── Log what was updated
```

## Working Rules

1. **JSON is Source of Truth**: deals.json is the authoritative copy. The Excel file is derived from it.
2. **Preserve Formatting**: Never overwrite headers, colors, column widths, or other formatting.
3. **Update Data Rows Only**: Replace data in rows 2+ while keeping row 1 (headers) intact.
4. **Log Changes**: Every sync operation creates a timestamped log entry showing what changed.
5. **Validate Mapping**: Use `references/field-mapping.md` to verify which JSON fields map to which Excel columns.
6. **Handle Missing Data**: Empty JSON fields should result in blank cells (not errors).
7. **Compare Before Write**: When syncing to Excel, only update cells that actually changed.

## Key References

- `references/field-mapping.md` - Exact JSON field to Excel column mappings
- `references/sync-log.txt` - Audit trail of all sync operations (auto-generated)

## Scripts

### scripts/sync_to_xlsx.py
**Primary sync: JSON → Excel**

- Reads `/fund/crm/deals.json`
- Reads `/projects/projects.json` (if exists)
- Updates `/fund/VFT-Master-Tracker.xlsx`
  - DD Pipeline tab with deal data
  - Project Management tab with project data
- Preserves all formatting and structure
- Logs changes to `references/sync-log.txt`

Usage:
```bash
python scripts/sync_to_xlsx.py
```

### scripts/sync_from_xlsx.py
**Reverse sync: Excel → JSON (optional)**

- Reads `/fund/VFT-Master-Tracker.xlsx`
- Compares data against current JSON files
- Updates `/fund/crm/deals.json` for changed deal rows
- Updates `/projects/projects.json` for changed project rows
- Logs what was synced to `references/sync-log.txt`

Usage:
```bash
python scripts/sync_from_xlsx.py [--dry-run]
```

The `--dry-run` flag shows what would change without actually writing.

## Example Workflow

1. **Update a deal in the CRM:**
   ```bash
   python scripts/upsert_deal.py --slug midbound --stage ic_ready
   ```

2. **Sync to the spreadsheet:**
   ```bash
   python scripts/sync_to_xlsx.py
   ```

3. **Share the updated spreadsheet** with the partnership team.

4. **If edits are made in Google Sheets**, pull them back:
   ```bash
   python scripts/sync_from_xlsx.py --dry-run  # Preview changes
   python scripts/sync_from_xlsx.py             # Apply changes
   ```

## Field Mapping

See `references/field-mapping.md` for the complete mapping of:
- JSON fields in deals.json → Excel columns in DD Pipeline tab
- JSON fields in projects.json → Excel columns in Project Management tab

Example:
- `company_name` → Column A (Company)
- `stage` → Column B (Stage)
- `status` → Column C (Status)
- etc.

## Data Validation

Before syncing:
- Validate that deals.json is well-formed JSON
- Validate that projects.json is well-formed JSON (if present)
- Ensure the Excel file is not locked by another process
- Check that all required JSON fields exist (with sensible defaults for missing data)

## Troubleshooting

**Q: The Excel file won't update**
- Check that the file path is correct: `/fund/VFT-Master-Tracker.xlsx`
- Ensure the file is not open/locked in another application
- Verify the JSON files are valid JSON

**Q: Headers got overwritten**
- This should not happen with the current scripts. If it does, the script has a bug.
- Always restore from the git repository: `git restore fund/VFT-Master-Tracker.xlsx`

**Q: Data looks wrong in the spreadsheet**
- Check `references/field-mapping.md` to ensure fields are mapped correctly
- Run the script with verbose output to see what's being written
- Compare the JSON source directly against the Excel result

**Q: Want to revert a bad sync**
- Restore from git: `git restore fund/VFT-Master-Tracker.xlsx`
- Or manually revert: `git checkout HEAD -- fund/VFT-Master-Tracker.xlsx`

## Dependencies

- Python 3.7+
- `openpyxl` - For reading/writing Excel files
- `json` - For reading JSON (standard library)

Install dependencies:
```bash
pip install openpyxl
```
