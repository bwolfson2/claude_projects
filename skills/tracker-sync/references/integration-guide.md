# Integration Guide: Tracker Sync with Fund Operations

This guide shows how tracker-sync integrates with other fund management tools and workflows.

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Fund Operations System                    │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    ┌─────────┐         ┌──────────┐        ┌──────────────┐
    │   CRM   │         │ Projects │        │ Diligence    │
    │  Data   │         │  Data    │        │ Outputs      │
    │(JSON)   │         │ (JSON)   │        │ (Markdown)   │
    └────┬────┘         └────┬─────┘        └──────────────┘
         │                   │
         └───────────┬───────┘
                     │
                     ▼
          ┌─────────────────────┐
          │   tracker-sync      │  ◄── YOU ARE HERE
          │  (this skill)       │
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │   VFT-Master-      │
          │   Tracker.xlsx      │
          │  (Reporting tool)   │
          └─────────────────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │   Share with        │
          │   Stakeholders      │
          │  (Email, Drive, etc)│
          └─────────────────────┘
```

## Workflow 1: Daily Deal Updates

The most common workflow: update deals in the CRM, sync to Excel.

### Sequence

```
1. Morning standup identifies action items
   └─ "Midbound founders sent updated cap table"

2. Update deal in CRM
   └─ Run: upsert_deal.py --slug midbound --diligence.finance_legal complete

3. Sync to Excel
   └─ Run: sync_to_xlsx.py

4. Share updated tracker with team
   └─ Upload to Google Drive or email the file

5. Team sees latest status
   └─ Informed decision-making at next meeting
```

### Command Sequence

```bash
# 1. Update the deal
cd /sessions/vigilant-dazzling-franklin/mnt/due_diligences
python3 skills/fund-dealflow-orchestrator/scripts/upsert_deal.py \
  --slug midbound \
  --diligence finance_legal complete

# 2. Sync to Excel
python3 skills/tracker-sync/scripts/sync_to_xlsx.py

# 3. Commit changes
git add fund/crm/deals.json fund/VFT-Master-Tracker.xlsx
git commit -m "Midbound: Finance/Legal DD now complete"

# 4. Share the file
# (upload to Drive, email, etc.)
```

## Workflow 2: Collaborative Spreadsheet Editing

When teams prefer editing the spreadsheet directly (e.g., in Google Sheets).

### Sequence

```
1. Download VFT-Master-Tracker.xlsx
   └─ Run: sync_to_xlsx.py first to ensure it's current

2. Upload to Google Sheets
   └─ Share with team for editing

3. Team makes edits for several days
   └─ Status updates, next action changes, priority adjustments

4. End of day: Pull changes back to JSON
   └─ Run: sync_from_xlsx.py --dry-run (review)
   └─ Run: sync_from_xlsx.py (apply)

5. Version control the changes
   └─ git add and commit

6. Download fresh copy from Sheets and re-sync next morning
```

### Command Sequence

```bash
cd /sessions/vigilant-dazzling-franklin/mnt/due_diligences

# Monday morning: Push latest JSON to Excel
python3 skills/tracker-sync/scripts/sync_to_xlsx.py

# Download to computer, upload to Google Sheets
# Team edits spreadsheet all week...

# Friday afternoon: Pull changes back
python3 skills/tracker-sync/scripts/sync_from_xlsx.py --dry-run
# Review the output...

python3 skills/tracker-sync/scripts/sync_from_xlsx.py
# Apply changes

# Commit
git add fund/crm/deals.json
git commit -m "Friday sync: Pull spreadsheet edits back to CRM"
```

## Workflow 3: Multi-Skill Integration

Using tracker-sync with other fund management skills for a complete workflow.

### Full Deal Lifecycle

```
Day 1: New Deal Sourced
  ├─ Run: fund-dealflow-orchestrator/init_company_workspace.py
  │   └─ Creates fund/companies/acme/ directory structure
  │   └─ Seeds deals.json with new company
  ├─ Run: tracker-sync/sync_to_xlsx.py
  │   └─ Excel now shows the new company
  └─ Share spreadsheet with partners

Week 1-2: Deep Diligence
  ├─ Run: various diligence scripts
  │   └─ commercial-diligence-review
  │   └─ product-technical-diligence
  │   └─ finance-legal-diligence
  ├─ Outputs collected in fund/companies/acme/
  ├─ Run: upsert_deal.py to update status and links
  │   └─ python3 upsert_deal.py \
  │       --slug acme \
  │       --diligence.commercial complete \
  │       --artifacts.commercial_report /path/to/report.md
  ├─ Run: tracker-sync/sync_to_xlsx.py
  │   └─ Excel shows progress
  └─ Share updated tracker

Week 3: Synthesis & Decision
  ├─ Run: diligence-memo-writer (creates memo.md)
  ├─ Run: upsert_deal.py to finalize status
  │   └─ python3 upsert_deal.py \
  │       --slug acme \
  │       --stage ic_ready \
  │       --decision_posture lean_yes \
  │       --artifacts.diligence_memo /path/to/memo.md
  ├─ Run: tracker-sync/sync_to_xlsx.py
  │   └─ Excel shows decision status
  ├─ IC votes on spreadsheet
  └─ Decision logged in tracker

Post-Decision: Follow-up
  ├─ If PASS: Update status and move to next
  │   └─ python3 upsert_deal.py --slug acme --status passed
  ├─ If YES: Continue to term sheet
  │   └─ python3 upsert_deal.py --slug acme --stage term_sheet
  ├─ Run: tracker-sync/sync_to_xlsx.py
  └─ Historical record maintained in tracker
```

## Workflow 4: Project Management Integration

Tracking fund-level projects (operations, legal, hiring, etc.).

### Setup

```bash
# 1. Create projects.json with fund initiatives
cp skills/tracker-sync/references/example-projects.json \
   projects/projects.json

# 2. Edit projects.json to add your actual projects
# (or populate via API)

# 3. Sync to Excel
python3 skills/tracker-sync/scripts/sync_to_xlsx.py

# 4. Share the "Project Management" tab with ops team
```

### Ongoing Management

```bash
# When project status changes (weekly/daily):
# Option A: Edit projects.json directly
#   └─ Use your favorite editor

# Option B: Edit in Google Sheets
#   └─ Upload Excel, team edits, pull back with sync_from_xlsx.py

# Then sync:
python3 skills/tracker-sync/scripts/sync_to_xlsx.py
git add projects/projects.json
git commit -m "Update project status: [project-name]"
```

## Data Flow Diagram: Complete Workflow

```
┌──────────────────────────────────────────────────────────────────┐
│                    Fund CRM Data Layer                           │
│  /fund/crm/deals.json  |  /projects/projects.json                │
│  (Version controlled)  |  (Version controlled)                   │
└────────────────┬───────────────────────────┬─────────────────────┘
                 │                           │
        ┌────────▼────────────┐    ┌────────▼──────────────┐
        │ fund-dealflow-      │    │ project-management   │
        │ orchestrator        │    │ (or manual editing)  │
        │ (upsert_deal.py)    │    │                      │
        └────────┬────────────┘    └────────┬──────────────┘
                 │                          │
        ┌────────▼──────────────────────────▼──────────┐
        │        tracker-sync (this skill)             │
        │  • sync_to_xlsx.py   (JSON → Excel)          │
        │  • sync_from_xlsx.py (Excel → JSON)          │
        └────────┬──────────────────────────┬──────────┘
                 │                          │
        ┌────────▼──────────┐      ┌────────▼────────────┐
        │ DD Pipeline tab   │      │Project Management  │
        │ (Reporting view)  │      │tab (Reporting view)│
        └────────┬──────────┘      └────────┬────────────┘
                 │                          │
        ┌────────▼──────────────────────────▼──────────┐
        │    VFT-Master-Tracker.xlsx                   │
        │    (Single, unified spreadsheet)             │
        └────────┬──────────────────────────┬──────────┘
                 │                          │
        ┌────────▼───────┐      ┌──────────▼──────┐
        │ Email to       │      │ Upload to       │
        │ stakeholders   │      │ Google Sheets   │
        │ (read-only)    │      │ (collaborative) │
        └────────────────┘      └─────────┬───────┘
                                          │
                                   ┌──────▼──────┐
                                   │ Team edits  │
                                   │ in Drive    │
                                   └──────┬──────┘
                                          │
                                   ┌──────▼──────────────────┐
                                   │ sync_from_xlsx.py      │
                                   │ pulls changes back to  │
                                   │ deals.json /           │
                                   │ projects.json          │
                                   └──────┬─────────────────┘
                                          │
                                   ┌──────▼──────────────┐
                                   │ git commit &        │
                                   │ version control     │
                                   └─────────────────────┘
```

## Best Practices for Integration

### 1. Sync Frequency

| Scenario | Frequency | Command |
|---|---|---|
| After every deal update | Immediate | `sync_to_xlsx.py` |
| Daily with CRM as source | Morning | `sync_to_xlsx.py` |
| Shared sheet editing | End of day | `sync_from_xlsx.py` |
| Weekly reporting | Weekly | `sync_to_xlsx.py` |
| Before meetings | As-needed | `sync_to_xlsx.py` |

### 2. Git Workflow

After every sync operation, commit changes:

```bash
# For JSON-to-Excel (normal case)
git add fund/VFT-Master-Tracker.xlsx
git commit -m "Sync: Update tracker from CRM"

# For Excel-to-JSON (reverse sync)
git add fund/crm/deals.json projects/projects.json
git commit -m "Sync: Pull spreadsheet edits back to CRM"

# For both
git add fund/crm/deals.json projects/projects.json fund/VFT-Master-Tracker.xlsx
git commit -m "Sync: Bidirectional spreadsheet sync"
```

### 3. File Ownership

- **JSON files** = primary source of truth (owned by CRM)
- **Excel file** = derived reporting (regenerated as needed)
- **Spreadsheet edits** = temporary (pulled back regularly)

### 4. Conflict Resolution

If JSON and Excel diverge:

```bash
# Option 1: Trust JSON (recommended)
git restore fund/VFT-Master-Tracker.xlsx
python3 skills/tracker-sync/scripts/sync_to_xlsx.py

# Option 2: Trust Excel edits
python3 skills/tracker-sync/scripts/sync_from_xlsx.py

# Option 3: Manual reconciliation
# Compare files, decide what's authoritative, then sync
```

## Troubleshooting Integration Issues

### Issue: Data looks wrong in Excel after sync

**Diagnosis**:
1. Check field mapping: `references/field-mapping.md`
2. Verify JSON is valid: `python3 -m json.tool fund/crm/deals.json`
3. Check sync log: `tail references/sync-log.txt`

**Solution**:
1. Fix the JSON data
2. Re-run sync_to_xlsx.py
3. Verify in Excel

### Issue: Can't sync from Excel back to JSON

**Diagnosis**:
1. Check that fund-dealflow-orchestrator has been initialized
2. Verify deals.json exists and is valid
3. Check the deals have company_name fields

**Solution**:
1. Initialize with fund-dealflow-orchestrator first
2. Ensure deals.json has valid structure
3. Run sync_from_xlsx.py --dry-run to see errors

### Issue: File permissions errors

**Diagnosis**: Script can't read/write files

**Solution**:
```bash
# Check permissions
ls -la fund/crm/deals.json
ls -la fund/VFT-Master-Tracker.xlsx

# Fix permissions if needed
chmod 644 fund/VFT-Master-Tracker.xlsx
chmod 644 fund/crm/deals.json
```

## Advanced Integration: Automation

### Scheduled Daily Sync

Create a cron job to sync daily:

```bash
# Add to crontab (crontab -e)
0 8 * * * cd /sessions/vigilant-dazzling-franklin/mnt/due_diligences && \
  python3 skills/tracker-sync/scripts/sync_to_xlsx.py >> /tmp/sync.log 2>&1

# This syncs every morning at 8 AM
```

### Automated Reverse Sync from Google Sheets

If using Google Drive with shared spreadsheet:

```bash
# Periodically download from Drive, then sync
# (Requires Drive API setup - more advanced)

# Simplified: Manual download, then sync
python3 skills/tracker-sync/scripts/sync_from_xlsx.py --dry-run
python3 skills/tracker-sync/scripts/sync_from_xlsx.py
```

## Integration Checklist

When setting up tracker-sync in your fund:

- [ ] Install dependencies: `pip install openpyxl`
- [ ] Verify JSON files exist and are valid
- [ ] Verify Excel file exists
- [ ] Run initial sync: `sync_to_xlsx.py`
- [ ] Test reverse sync: `sync_from_xlsx.py --dry-run`
- [ ] Review field mappings in `references/field-mapping.md`
- [ ] Set up git commits for sync operations
- [ ] Share sync log location with team
- [ ] Document sync schedule for team
- [ ] Train team on when to use each sync direction
- [ ] Create team guidelines for JSON vs Sheets editing
- [ ] Test full workflow (create deal → sync → share)

---

**Last Updated**: 2026-03-10
**Version**: 1.0
