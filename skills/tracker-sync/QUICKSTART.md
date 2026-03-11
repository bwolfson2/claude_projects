# Tracker Sync - Quick Start Guide

**TL;DR**: Sync your local JSON CRM data to the Excel spreadsheet and back.

## Installation

```bash
pip install openpyxl
```

## The One Command You'll Use Most

After updating deals in the CRM, sync to Excel:

```bash
cd /sessions/vigilant-dazzling-franklin/mnt/due_diligences
python3 skills/tracker-sync/scripts/sync_to_xlsx.py
```

Done! The Excel file is updated.

## The Other Command (For Spreadsheet Edits)

If the spreadsheet is shared for team editing, pull changes back:

```bash
# First, preview what will change
python3 skills/tracker-sync/scripts/sync_from_xlsx.py --dry-run

# If it looks good, apply changes
python3 skills/tracker-sync/scripts/sync_from_xlsx.py
```

## Common Workflows

### Workflow A: Update Deal → Share

```bash
# 1. Update deal in CRM
python3 skills/fund-dealflow-orchestrator/scripts/upsert_deal.py \
  --slug midbound --stage ic_ready

# 2. Sync to Excel
python3 skills/tracker-sync/scripts/sync_to_xlsx.py

# 3. Share the updated spreadsheet
# (email, upload to Drive, etc.)
```

### Workflow B: Team Edits Spreadsheet → Pull Back

```bash
# 1. Team edits in Google Sheets

# 2. Pull changes back to JSON
python3 skills/tracker-sync/scripts/sync_from_xlsx.py --dry-run
python3 skills/tracker-sync/scripts/sync_from_xlsx.py

# 3. Commit to git
git add fund/crm/deals.json
git commit -m "Sync: Pull spreadsheet edits"
```

## File Locations

| File | Location | Purpose |
|---|---|---|
| Deals Data | `fund/crm/deals.json` | Source of truth for deals |
| Projects Data | `projects/projects.json` | Source of truth for projects |
| Excel Tracker | `fund/VFT-Master-Tracker.xlsx` | Spreadsheet for sharing |
| Sync Scripts | `skills/tracker-sync/scripts/` | Sync automation |

## Key Rules

1. **JSON is source of truth** - Update JSON first, then sync to Excel
2. **Sync before sharing** - Always run `sync_to_xlsx.py` before sharing the spreadsheet
3. **Dry-run for reverse sync** - Always preview with `--dry-run` before pulling Excel changes back
4. **Version control** - Commit after every sync operation

## What Gets Synced

### From JSON → Excel
- **DD Pipeline tab**: All deal records with status, stage, diligence progress, next actions
- **Project Management tab**: All projects with status, owner, next actions
- **Headers & Formatting**: Preserved automatically

### From Excel → JSON
- **Deal updates**: Any changed values in the spreadsheet
- **Project updates**: Any changed values in the spreadsheet
- **Data types**: Automatically converted (strings, numbers, dates)

## Files to Know

```
tracker-sync/
├── SKILL.md                    # Overview & working rules
├── README.md                   # Complete documentation
├── QUICKSTART.md              # This file
├── scripts/
│   ├── sync_to_xlsx.py        # JSON → Excel (use this most)
│   └── sync_from_xlsx.py      # Excel → JSON (optional)
├── references/
│   ├── field-mapping.md       # JSON field ↔ Excel column mapping
│   ├── integration-guide.md   # How it fits into fund operations
│   ├── example-projects.json  # Template for projects.json
│   └── sync-log.txt          # Audit trail of all syncs
```

## Troubleshooting

| Problem | Solution |
|---|---|
| "Excel file not found" | Verify path: `ls fund/VFT-Master-Tracker.xlsx` |
| "deals.json not valid" | Check JSON: `python3 -m json.tool fund/crm/deals.json` |
| "File is locked" | Close the Excel file in all applications |
| "Data looks wrong" | Check `references/field-mapping.md` for correct mappings |
| "Dry-run shows unexpected changes" | Review output, then decide to apply or revert |

## Next Steps

- **First time?** Read `README.md` for detailed documentation
- **Integrating with other skills?** Check `references/integration-guide.md`
- **Want to understand the mappings?** See `references/field-mapping.md`
- **Need to debug?** Check `references/sync-log.txt` for audit trail

## Support

For questions or issues:
1. Check `README.md` troubleshooting section
2. Review `references/sync-log.txt` for what actually happened
3. Run with verbose flag: `python3 scripts/sync_to_xlsx.py --verbose`

---

**Ready to sync?** Run this:

```bash
cd /sessions/vigilant-dazzling-franklin/mnt/due_diligences
python3 skills/tracker-sync/scripts/sync_to_xlsx.py
```

That's it!
