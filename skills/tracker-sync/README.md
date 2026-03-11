# Tracker Sync Skill - Usage Guide

This guide explains how to use the tracker-sync skill to synchronize data between your local JSON CRM and the master Excel spreadsheet.

## Overview

The tracker-sync skill maintains bidirectional synchronization between:

- **JSON Files** (source of truth, version-controlled)
  - `/fund/crm/deals.json` - Deal pipeline data
  - `/projects/projects.json` - Project management data

- **Excel Spreadsheet** (reporting & collaboration)
  - `/fund/VFT-Master-Tracker.xlsx`
    - DD Pipeline tab (deals)
    - Project Management tab (projects)
    - DD Checklist tab (read-only reference)

## Quick Start

### 1. Sync JSON to Excel (Most Common)

After updating deal data in the CRM, sync to Excel:

```bash
cd /sessions/vigilant-dazzling-franklin/mnt/due_diligences
python3 skills/tracker-sync/scripts/sync_to_xlsx.py
```

This will:
- Read `/fund/crm/deals.json`
- Read `/projects/projects.json` (if exists)
- Update the Excel file with current data
- Preserve all formatting and structure
- Log all changes

### 2. Sync Excel to JSON (Optional - When Using Google Sheets)

If the spreadsheet is shared for collaborative editing in Google Sheets, pull changes back:

```bash
# First, preview what will change:
python3 skills/tracker-sync/scripts/sync_from_xlsx.py --dry-run

# Then apply changes:
python3 skills/tracker-sync/scripts/sync_from_xlsx.py
```

This will:
- Read the Excel file
- Compare data against current JSON
- Update JSON files with any changes
- Log what was modified

## Typical Workflow

### Scenario 1: Update a Deal, Then Share

```bash
# 1. Update deal in the CRM using fund-dealflow-orchestrator
python3 skills/fund-dealflow-orchestrator/scripts/upsert_deal.py \
  --slug midbound \
  --stage ic_ready \
  --decision_posture lean_yes

# 2. Sync the update to Excel
python3 skills/tracker-sync/scripts/sync_to_xlsx.py

# 3. Share the updated spreadsheet with stakeholders
# (email, upload to drive, etc.)
```

### Scenario 2: Shared Spreadsheet Editing

```bash
# 1. Team edits the spreadsheet in Google Sheets

# 2. At the end of the day, pull changes back into JSON
python3 skills/tracker-sync/scripts/sync_from_xlsx.py --dry-run

# Review the proposed changes (the dry-run output shows what will change)

# 3. If changes look good, apply them
python3 skills/tracker-sync/scripts/sync_from_xlsx.py

# 4. Commit the changes to git
git add fund/crm/deals.json projects/projects.json
git commit -m "Sync project updates from spreadsheet"
```

### Scenario 3: Initialize Projects File

If you don't have a `projects.json` file yet:

```bash
# 1. Create the file with initial structure
cp skills/tracker-sync/references/example-projects.json projects/projects.json

# 2. Edit as needed to add your actual projects

# 3. Sync to Excel
python3 skills/tracker-sync/scripts/sync_to_xlsx.py
```

## Script Details

### sync_to_xlsx.py

**Primary use**: Sync JSON CRM data to Excel for reporting and sharing.

**Command**:
```bash
python3 scripts/sync_to_xlsx.py [--verbose]
```

**What it does**:
1. Reads deals.json and projects.json
2. Clears data rows (rows 2+) in Excel tabs
3. Writes all records to Excel, preserving formatting
4. Logs changes to sync-log.txt
5. Never modifies headers or formatting

**Flags**:
- `--verbose`: Show detailed output for each record synced

**When to use**:
- After updating deal data with upsert_deal
- After adding or modifying projects
- Before sharing the spreadsheet
- Regular refresh (daily/weekly)

**Guarantees**:
- Headers are never overwritten
- Formatting is preserved
- Existing structure is respected
- No data is lost (old records are updated, not deleted)

### sync_from_xlsx.py

**Primary use**: Pull changes from a shared Google Sheet back into JSON.

**Command**:
```bash
python3 scripts/sync_from_xlsx.py [--dry-run] [--verbose]
```

**What it does**:
1. Reads the Excel file
2. Compares against current JSON records
3. Identifies what changed
4. Optionally updates JSON files (unless --dry-run)
5. Logs all changes

**Flags**:
- `--dry-run`: Preview changes without writing (recommended first step)
- `--verbose`: Show output for each record

**When to use**:
- After the spreadsheet is shared for collaborative editing
- To pull manual corrections from Excel back into JSON
- Periodically if Sheets is the collaborative interface

**Caution**:
- This modifies JSON files!
- Always use --dry-run first to review
- Commit changes to git after running

## Understanding the Data Flow

### JSON → Excel (Primary Direction)

```
Step 1: JSON is source of truth
  ├─ deals.json contains all deal data
  └─ projects.json contains all project data

Step 2: Sync to Excel
  ├─ Read JSON files
  ├─ Extract and transform data
  ├─ Write to Excel (preserving formatting)
  └─ Log what was written

Step 3: Share the spreadsheet
  └─ Send to stakeholders, upload to Drive, etc.
```

### Excel → JSON (Reverse Sync - Optional)

```
Step 1: Spreadsheet is shared for editing
  └─ Team members edit in Google Sheets

Step 2: Pull changes back into JSON
  ├─ Read Excel file
  ├─ Compare against current JSON
  ├─ Identify differences
  └─ Write updated JSON

Step 3: Version control the changes
  └─ Commit to git
```

## Field Mapping

The mapper between JSON and Excel is documented in `references/field-mapping.md`.

**Key mappings for deals**:
- `company_name` → Column A (Company)
- `stage` → Column B (Stage)
- `status` → Column C (Status)
- `raise_usd` → Column G (Raise)
- `diligence.*` → Columns P-S (DD Status)
- `open_questions` → Column T (one per line)
- `assumptions` → Column U (one per line)

**Key mappings for projects**:
- `name` → Column A (Project)
- `category` → Column B (Category)
- `status` → Column C (Status)
- `priority` → Column D (Priority)
- `owner` → Column E (Owner)
- `next_action_due` → Column K (Due Date)

See the full mapping in `references/field-mapping.md`.

## Sync Log

Every sync operation is logged in `references/sync-log.txt`.

Example log entries:
```
[2026-03-10 07:28:58] INFO: === Starting JSON → Excel sync ===
[2026-03-10 07:28:58] INFO: Loaded Excel workbook: ...
[2026-03-10 07:28:58] INFO: Found 5 companies to sync
[2026-03-10 07:28:58] INFO: Synced 5 companies to DD Pipeline tab
[2026-03-10 07:28:58] INFO: Saved Excel workbook: ...
[2026-03-10 07:28:58] INFO: === Sync completed successfully ===
```

This log is useful for:
- Auditing what changed
- Troubleshooting sync issues
- Verifying historical syncs

## Troubleshooting

### "Excel file won't update"

**Cause**: File is locked or inaccessible

**Solution**:
1. Close the Excel file in all applications
2. Verify the file path is correct
3. Check file permissions

```bash
# Verify the file exists and is readable
ls -la /sessions/vigilant-dazzling-franklin/mnt/due_diligences/fund/VFT-Master-Tracker.xlsx

# Check for lock files
ls -la /sessions/vigilant-dazzling-franklin/mnt/due_diligences/fund/.~lock.*
```

### "Data looks wrong after sync"

**Cause**: Incorrect field mapping or malformed JSON

**Solution**:
1. Check the field mapping in `references/field-mapping.md`
2. Verify JSON is well-formed:
   ```bash
   python3 -m json.tool fund/crm/deals.json > /dev/null
   ```
3. Compare JSON against Excel manually
4. Check the sync log for warnings

### "Headers got overwritten"

**Cause**: This shouldn't happen with the current script (bug if it does)

**Solution**:
1. Restore from git:
   ```bash
   git restore fund/VFT-Master-Tracker.xlsx
   ```
2. Run the script again
3. Report the issue if it persists

### "Dry run shows unexpected changes"

**Cause**: The JSON and Excel are out of sync

**Solution**:
1. Review the dry-run output carefully
2. If you trust the JSON, discard Excel changes:
   ```bash
   git restore fund/VFT-Master-Tracker.xlsx
   python3 scripts/sync_to_xlsx.py
   ```
3. If you trust the Excel edits, review them before applying reverse sync

## Best Practices

### 1. Keep JSON as Source of Truth

- Prefer updating deals in the CRM (via upsert_deal)
- Excel is for reporting and sharing, not editing
- If edits must be made in Excel, pull them back into JSON regularly

### 2. Sync Before Sharing

Always sync the JSON to Excel before sharing the spreadsheet:

```bash
python3 scripts/sync_to_xlsx.py
# Then share the file
```

### 3. Use Dry-Run for Reverse Syncs

Always preview with --dry-run before applying reverse syncs:

```bash
python3 scripts/sync_from_xlsx.py --dry-run
# Review the output
python3 scripts/sync_from_xlsx.py  # Only if changes look correct
```

### 4. Version Control

Commit changes to git after syncing:

```bash
git add fund/crm/deals.json projects/projects.json
git commit -m "Sync CRM updates to spreadsheet"

# Or after reverse sync:
git add fund/crm/deals.json projects/projects.json
git commit -m "Sync spreadsheet edits back to CRM"
```

### 5. Regular Syncs

If the spreadsheet is shared for collaborative editing, sync daily:

```bash
# Each morning:
python3 scripts/sync_from_xlsx.py --dry-run  # Review
python3 scripts/sync_from_xlsx.py             # Apply

# Before end of day:
git add fund/crm/deals.json projects/projects.json
git commit -m "Daily sync from shared spreadsheet"
```

## Setup & Dependencies

### Python Requirements

```bash
pip install openpyxl
```

### File Structure

```
tracker-sync/
├── SKILL.md                          # Overview & working rules
├── README.md                         # This file
├── scripts/
│   ├── sync_to_xlsx.py              # JSON → Excel (primary)
│   └── sync_from_xlsx.py            # Excel → JSON (optional)
├── references/
│   ├── field-mapping.md             # JSON ↔ Excel field mapping
│   ├── example-projects.json        # Template for projects.json
│   └── sync-log.txt                 # Audit log (auto-generated)
```

### Initial Setup

1. Install dependencies:
   ```bash
   pip install openpyxl
   ```

2. Verify JSON files exist:
   ```bash
   # deals.json should exist
   ls fund/crm/deals.json

   # projects.json is optional (will be created if needed)
   ls projects/projects.json
   ```

3. Verify Excel file exists:
   ```bash
   ls fund/VFT-Master-Tracker.xlsx
   ```

4. Run initial sync:
   ```bash
   python3 scripts/sync_to_xlsx.py
   ```

## Integration with Other Skills

This skill works with other fund management skills:

### fund-dealflow-orchestrator

Use together for complete deal management:

```bash
# 1. Update deal in CRM
python3 ../fund-dealflow-orchestrator/scripts/upsert_deal.py \
  --slug midbound --stage ic_ready

# 2. Sync to Excel
python3 scripts/sync_to_xlsx.py

# 3. Optionally, regenerate dashboard
python3 ../fund-dealflow-orchestrator/scripts/render_dealflow_dashboard.py
```

### project-management

Use together for project tracking:

```bash
# 1. Update project in projects.json manually or via API

# 2. Sync to Excel
python3 scripts/sync_to_xlsx.py

# 3. Share for team visibility
```

## Advanced Usage

### Verbose Sync with Logging

For detailed output and debugging:

```bash
python3 scripts/sync_to_xlsx.py --verbose 2>&1 | tee sync-output.log
```

### Checking What Changed

Review the sync log:

```bash
tail -20 references/sync-log.txt
```

### Custom Field Mappings (Advanced)

To modify field mappings, edit the `field_mapping` list in the sync scripts:

```python
field_mapping = [
    ("company_name", "A"),
    ("stage", "B"),
    # ... add or modify as needed
]
```

Then update `references/field-mapping.md` to document the change.

## Support & Troubleshooting

If you encounter issues:

1. Check the sync log: `cat references/sync-log.txt`
2. Run with verbose flag: `python3 scripts/sync_to_xlsx.py --verbose`
3. Verify JSON is valid: `python3 -m json.tool fund/crm/deals.json`
4. Check file permissions and paths
5. Review `references/field-mapping.md` for field definitions

For persistent issues, restore from git and try again:

```bash
git restore fund/VFT-Master-Tracker.xlsx
python3 scripts/sync_to_xlsx.py --verbose
```

---

**Last Updated**: 2026-03-10
**Version**: 1.0
**Status**: Ready for production use
