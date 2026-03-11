---
description: Scan all communication channels, classify messages, and update project registries
---

# /scan-comms

> Run a full communications scan across all connected channels.

Scan communications and process updates. $ARGUMENTS

## Execution

1. **Run the comms-hub pipeline:**
   ```bash
   python skills/comms-hub/scripts/run_pipeline.py
   ```

2. **Classify any new messages:**
   ```bash
   python skills/deal-project-classifier/scripts/classify_batch.py
   ```

3. **Apply updates to deals and projects:**
   ```bash
   python skills/deal-project-classifier/scripts/apply_updates.py
   ```

4. **Render fresh dashboard:**
   ```bash
   python skills/project-tracker/scripts/render_unified_dashboard.py
   ```

5. Present a summary of:
   - New messages found (by channel)
   - Messages classified to existing deals/projects
   - New deals or projects auto-created
   - Action items extracted

## Connected Channels

This command dispatches to whichever scanners are configured:
- **Email** — Outlook via Claude in Chrome
- **Slack** — Slack workspace via Chrome or MCP connector
- **WhatsApp** — WhatsApp Web via Chrome
- **Signal** — Signal Desktop via signal-cli or Chrome
- **Transcripts** — Meeting transcripts from Granola MCP

## Related Skills

- **comms-hub** — Master communication orchestrator
- **email-scanner**, **slack-scanner**, **whatsapp-scanner**, **signal-scanner** — Individual channel scanners
- **deal-project-classifier** — Message classification engine
