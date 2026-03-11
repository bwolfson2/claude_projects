---
name: project-tracker
description: Render a unified dashboard showing all project types (DD deals, hiring, research, conversations, operations) with status, priority, owner, last activity, and next actions. Use when checking overall status, asking "what's the status of everything", or needing a current view across all work streams.
---

# Unified Project Tracker

Render a single dashboard that spans all project types. Combines data from deals.json and projects.json into one view, grouped by type with activity summaries from the unified messages table.

## Trigger Phrases

- "What's the status of everything?"
- "Show me the dashboard"
- "What's active right now?"
- "What needs attention?"
- "Update the tracker"

## Core Workflow

1. Run `scripts/render_unified_dashboard.py` to generate `dashboard.md` at the repo root.
2. The script reads:
   - `fund/crm/deals.json` — DD pipeline
   - `projects/projects.json` — All other project types
   - `fund/metadata/db/ingestion.db` — Message counts and last activity per project
3. Also re-renders the type-specific dashboards:
   - `fund/crm/dashboard.md` (deals)
   - `projects/dashboard.md` (projects)
4. Optionally sync to Excel via tracker-sync skill.

## Dashboard Sections

1. **Summary** — Total counts by type and status
2. **Due Diligence Pipeline** — Active deals with stage, posture, raise, next action
3. **Hiring** — Active roles with stage, candidate count, next action
4. **Research** — Active research projects with status and key findings summary
5. **Conversations** — Active tracked relationships with last message date
6. **Operations** — Active ops projects with status and next action
7. **Needs Attention** — Items with overdue actions or stale last_touch

## Scripts

- `scripts/render_unified_dashboard.py`
  - `--output dashboard.md` — Output path (default: repo root)
  - `--include-message-counts` — Add message counts per project from ingestion DB

## Working Rules

- Sort projects by last activity (most recent first) within each section.
- Flag items with no activity in 7+ days in "Needs Attention".
- Include message counts from the unified messages table when available.
- Preserve existing type-specific dashboards (don't replace, supplement).
