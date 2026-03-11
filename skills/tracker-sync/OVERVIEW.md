# Tracker Sync Skill - Complete Overview

## What This Skill Does

The **tracker-sync** skill maintains bidirectional synchronization between:

- **JSON Files** (version-controlled source of truth)
  - `/fund/crm/deals.json` - Deal pipeline and company data
  - `/projects/projects.json` - Project management data

- **Excel Spreadsheet** (reporting and collaboration tool)
  - `/fund/VFT-Master-Tracker.xlsx` with multiple tabs:
    - DD Pipeline (deal data)
    - Project Management (project data)
    - DD Checklist (reference)

This is the **integration layer** that bridges your CRM system and spreadsheet-based reporting.

## Quick Start

### Most Common Use: Sync JSON to Excel

```bash
cd /sessions/vigilant-dazzling-franklin/mnt/due_diligences
python3 skills/tracker-sync/scripts/sync_to_xlsx.py
```

This reads deals.json and projects.json, then updates the Excel file.

### Optional: Sync Excel Back to JSON

When the spreadsheet is shared for collaborative editing:

```bash
python3 skills/tracker-sync/scripts/sync_from_xlsx.py --dry-run  # Preview
python3 skills/tracker-sync/scripts/sync_from_xlsx.py             # Apply
```

## Key Features

✓ **Bidirectional Sync**
  - JSON → Excel (primary)
  - Excel → JSON (optional, for spreadsheet edits)

✓ **Preserves Formatting**
  - Headers never overwritten
  - Column widths maintained
  - Cell colors preserved
  - Multi-line text supported

✓ **Comprehensive Logging**
  - Every sync operation logged
  - Audit trail in `references/sync-log.txt`
  - Timestamps and change details

✓ **Safe Operations**
  - Dry-run preview mode available
  - No destructive changes without explicit command
  - Comparison before writing

✓ **Complete Data Mapping**
  - Handles complex fields (arrays, nested objects)
  - Type conversion (strings, numbers, dates)
  - Empty field handling

## File Structure

```
tracker-sync/
│
├── SKILL.md                     # Skill definition & operating rules
├── README.md                    # Complete usage documentation
├── QUICKSTART.md               # Quick reference for common tasks
├── OVERVIEW.md                 # This file
│
├── scripts/
│   ├── sync_to_xlsx.py        # Primary: JSON → Excel
│   └── sync_from_xlsx.py      # Optional: Excel → JSON
│
└── references/
    ├── field-mapping.md        # Complete JSON ↔ Excel field mappings
    ├── integration-guide.md    # How it fits in fund operations
    ├── example-projects.json   # Template for projects.json
    └── sync-log.txt           # Audit trail (auto-generated)
```

## Documentation Guide

| Document | Purpose | Read When |
|---|---|---|
| **QUICKSTART.md** | Fast reference | You're in a hurry |
| **SKILL.md** | Overview & rules | Learning what this skill does |
| **README.md** | Complete guide | You want detailed documentation |
| **OVERVIEW.md** | This document | You're exploring the skill |
| **field-mapping.md** | Data mapping | Understanding JSON ↔ Excel fields |
| **integration-guide.md** | System integration | Using with other fund skills |
| **example-projects.json** | Template | Setting up projects.json |

## How It Works

### Sync Direction 1: JSON → Excel (Normal)

```
Input:  deals.json & projects.json (local JSON files)
        ↓
Process: 1. Read JSON files
         2. Transform data for Excel
         3. Write to spreadsheet (preserving format)
         4. Log all changes
        ↓
Output: VFT-Master-Tracker.xlsx (updated spreadsheet)
```

**Use Case**: After updating deals in the CRM, sync to Excel for sharing with stakeholders.

### Sync Direction 2: Excel → JSON (Optional)

```
Input:  VFT-Master-Tracker.xlsx (edited spreadsheet)
        ↓
Process: 1. Read Excel tabs
         2. Compare against current JSON
         3. Identify changes
         4. Update JSON files
         5. Log what changed
        ↓
Output: deals.json & projects.json (updated JSON)
```

**Use Case**: Team makes edits in a shared Google Sheet, pull changes back to JSON for version control.

## Data Synced

### Deals (DD Pipeline Tab)

From `deals.json` → Excel columns:

- Company name, stage, status
- Decision posture, sector, round size
- Raise and valuation details
- Owner and priority
- Last touch and next action tracking
- Thesis and open questions
- Assumptions
- Diligence status (commercial, product/tech, finance/legal, memo)

### Projects (Project Management Tab)

From `projects.json` → Excel columns:

- Project name, category, status
- Priority and owner
- Start date, target date
- Description, next action, next action owner
- Due dates and artifacts/links
- Notes

## Working Rules

1. **JSON is source of truth**
   - Always update JSON first
   - Excel is derived/reporting view

2. **Sync before sharing**
   - Run `sync_to_xlsx.py` before sending spreadsheet to stakeholders

3. **Dry-run for reverse syncs**
   - Always use `--dry-run` before applying Excel → JSON changes

4. **Version control**
   - Commit after every sync: `git add . && git commit -m "Sync: ..."`

5. **Preserve formatting**
   - Scripts never modify headers or formatting
   - Only data rows (row 2+) are updated

6. **Log everything**
   - Every operation logged to `references/sync-log.txt`
   - Audit trail for tracking changes

## Integration with Other Skills

This skill works seamlessly with:

- **fund-dealflow-orchestrator**: Update deals with `upsert_deal.py`, then sync to Excel
- **project-management**: Manage projects in JSON, then sync to Excel
- **diligence-memo-writer**: Outputs integrated via deals.json artifacts
- **Commercial/Product/Finance Diligence**: Status tracked in JSON, synced to Excel

## Common Workflows

### Daily Deal Updates

```bash
1. Update deal: upsert_deal.py
2. Sync: sync_to_xlsx.py
3. Share: Upload to Drive/email
4. Commit: git add & commit
```

### Collaborative Spreadsheet

```bash
1. Sync to Excel: sync_to_xlsx.py
2. Share spreadsheet in Google Sheets
3. Team edits all week
4. Pull back: sync_from_xlsx.py --dry-run, then sync_from_xlsx.py
5. Commit: git add & commit
```

### Multi-Skill Deal Workflow

```bash
1. Init company: fund-dealflow-orchestrator
2. Run diligence: multiple diligence skills
3. Update status: upsert_deal.py
4. Sync to tracker: sync_to_xlsx.py
5. Share & decide: Email/IC vote
6. Update status: upsert_deal.py
7. Final sync: sync_to_xlsx.py
```

## Dependencies

- **Python 3.7+**
- **openpyxl 3.0+** (for Excel manipulation)

Install dependencies:
```bash
pip install openpyxl
```

## File Paths Reference

| What | Path |
|---|---|
| Deals data | `/fund/crm/deals.json` |
| Projects data | `/projects/projects.json` |
| Excel tracker | `/fund/VFT-Master-Tracker.xlsx` |
| Sync to Excel script | `/skills/tracker-sync/scripts/sync_to_xlsx.py` |
| Sync from Excel script | `/skills/tracker-sync/scripts/sync_from_xlsx.py` |
| Field mapping docs | `/skills/tracker-sync/references/field-mapping.md` |
| Sync log | `/skills/tracker-sync/references/sync-log.txt` |
| This skill's root | `/skills/tracker-sync/` |

## Key Concepts

### Source of Truth

The **JSON files** are the authoritative source:
- Version controlled in git
- Structurally validated
- Used by all tools and scripts
- Excel is derived from these

### Derived Reporting

The **Excel spreadsheet** is a reporting view:
- Generated from JSON
- Shared with stakeholders
- Can be edited in Google Sheets temporarily
- Changes pulled back to JSON regularly

### Field Mapping

**Field mapping** defines which JSON fields map to which Excel columns:
- Documented in `references/field-mapping.md`
- Handles data transformation
- Supports nested objects and arrays
- Type conversion automatic

### Audit Trail

**Sync log** maintains complete history:
- Timestamps for every sync
- What was synced
- Errors or warnings
- Located in `references/sync-log.txt`

## Typical Setup

1. **Install dependencies**
   ```bash
   pip install openpyxl
   ```

2. **Verify JSON files exist**
   ```bash
   ls fund/crm/deals.json        # Should exist
   ls projects/projects.json      # Optional (created as needed)
   ```

3. **Verify Excel file exists**
   ```bash
   ls fund/VFT-Master-Tracker.xlsx
   ```

4. **Run first sync**
   ```bash
   python3 skills/tracker-sync/scripts/sync_to_xlsx.py
   ```

5. **Check the sync log**
   ```bash
   tail skills/tracker-sync/references/sync-log.txt
   ```

6. **Set up git commits**
   ```bash
   git add fund/VFT-Master-Tracker.xlsx
   git commit -m "Initial sync: Load data from JSON to Excel"
   ```

## Troubleshooting Quick Links

- **Excel file not found?** → Check file path and permissions
- **JSON validation errors?** → Verify JSON is valid
- **Data looks wrong?** → Check field-mapping.md
- **File is locked?** → Close Excel, check for lock files
- **Unexpected changes?** → Use --dry-run and review carefully

For detailed troubleshooting, see README.md.

## Support & Documentation

- **Quick questions?** → QUICKSTART.md
- **How to use?** → README.md  
- **System integration?** → integration-guide.md
- **Field definitions?** → field-mapping.md
- **Working rules?** → SKILL.md

## Status

✅ **Production Ready**
- Tested and working
- Complete documentation
- Safe operations with dry-run support
- Comprehensive logging
- Integration with other fund skills

## Version

- **Current Version**: 1.0
- **Last Updated**: 2026-03-10
- **Status**: Stable & Ready for Use

---

**Ready to use?** Start with QUICKSTART.md or README.md.
