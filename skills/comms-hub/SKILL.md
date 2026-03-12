---
name: comms-hub
description: Master orchestrator that dispatches all communication scanners, runs classification, updates project registries, and renders a fresh dashboard. Use when checking messages, running a full pipeline update, or asking "what's new" across all communication channels.
---

# Communications Hub

The master orchestrator for the VFT project management system. Coordinates all scanners, classifiers, and dashboard renderers into a single pipeline.

## Trigger Phrases

- "Check my messages"
- "What's new?"
- "Update everything"
- "Run the full pipeline"
- "What's new on [project]?"

## Full Pipeline Workflow

When triggered with "Check my messages" or "Update everything":

1. **Dispatch scanners** (in parallel where possible):
   - `email-scanner` — Scan Outlook inbox (ms365 MCP or Chrome fallback)
   - `slack-scanner` — Scan Slack channels (connector first, Chrome fallback)
   - `whatsapp-scanner` — Scan WhatsApp (MCP or Chrome fallback)
   - `signal-scanner` — Scan Signal (signal-cli or Chrome)
   - `transcript-ingestion` — Pull new Granola transcripts
   - `calendar-scanner` — Scan calendar events (Google Calendar or Outlook Calendar MCP, else Chrome)

2. **Classify new messages**:
   - Run `deal-project-classifier` on all unclassified messages
   - Use `scripts/classify_messages.py` (v2, unified table)
   - Apply updates to deals.json and projects.json

3. **Render dashboards**:
   - Run `project-tracker` unified dashboard
   - Re-render type-specific dashboards

4. **Report summary**:
   - "X new messages ingested (Y from Outlook, Z from Slack, ...)"
   - "A classified to existing projects, B auto-created new entries"
   - "C items need attention (stale or unclassified)"

## Project-Specific Query

When triggered with "What's new on [project]?":

1. Look up the project slug in deals.json or projects.json.
2. Query the unified messages table for messages tagged to that project.
3. Summarize recent activity: new messages, updated status, pending actions.
4. Show the project's current next-actions.

## Scripts

- `scripts/run_pipeline.py`
  - `--scanners all|outlook|slack|whatsapp|signal|granola|calendar` — Which scanners to run
  - `--classify` — Run classifier after scanning (default: true)
  - `--dashboard` — Render dashboard after classification (default: true)
  - `--dry-run` — Preview without changes
  - `--project SLUG` — Filter to a specific project

## Scanner Dispatch Order

Scanners are dispatched in this order (connector-first, Chrome fallback):
1. Granola transcripts (MCP connector — fastest, no browser needed)
2. Outlook emails (ms365 MCP or Chrome)
3. Slack messages (connector if available, else Chrome)
4. WhatsApp messages (MCP or Chrome)
5. Signal messages (signal-cli if available, else Chrome)
6. Calendar events (Google Calendar or Outlook Calendar MCP, else Chrome)

If `fund/metadata/config.json` exists, only enabled channels are dispatched.

If a scanner fails, log the error and continue with the next. Never let one scanner failure block the pipeline.

## Working Rules

- Always run the full pipeline end-to-end unless the user specifies otherwise.
- Report results at each stage (scanning → classification → dashboard).
- If no new messages, report "No new messages" cleanly.
- For project-specific queries, filter the messages table by project_tags.
- After pipeline completes, always show the "Needs Attention" items.

## Cron Integration

The comms-hub is designed to be called by a scheduled task every 2 hours Mon-Fri.
The scheduled task runs the full pipeline with default settings.
