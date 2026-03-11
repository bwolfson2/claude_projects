---
description: Set up or manage scheduled monitoring — configure automated scanning intervals for all communication channels
---

# /watch

> Configure automated monitoring schedules for all data feeds.

Manage watch schedules. $ARGUMENTS

## Execution

### If no arguments: Show current schedule and offer setup

Check existing scheduled tasks and present the current monitoring configuration.

### Default Schedule

Set up these scheduled tasks using Claude Code's scheduled task system:

| Task ID | Schedule | What It Does |
|---------|----------|-------------|
| `vft-email-scan` | Every 4h weekdays (9,13,17,21) | Scan Outlook inbox → classify → apply |
| `vft-slack-scan` | Every 2h weekdays (9,11,13,15,17,19) | Scan Slack channels → classify → apply |
| `vft-whatsapp-scan` | Every 4h weekdays (9,13,17,21) | Scan WhatsApp groups → classify → apply |
| `vft-signal-scan` | Every 4h weekdays (9,13,17,21) | Scan Signal messages → classify → apply |
| `vft-transcript-ingest` | Daily at 9am weekdays | Pull Granola transcripts → classify → apply |
| `vft-full-classify` | Every 2h weekdays (8,10,12,14,16,18,20) | Classify unprocessed items → route → apply |
| `vft-monitor-sweep` | Daily at 8am weekdays | Full /monitor sweep with reactive routing |

### Creating Scheduled Tasks

For each task, use the scheduled tasks system:

**Email scanning (every 4 hours, weekdays):**
- Task ID: `vft-email-scan`
- Cron: `0 9,13,17,21 * * 1-5`
- Prompt: "Run /vft-fund-tools:scan-comms with email scanner only. Scan Outlook inbox for new messages, classify them, and apply updates to deals and projects."

**Slack scanning (every 2 hours, weekdays):**
- Task ID: `vft-slack-scan`
- Cron: `0 9,11,13,15,17,19 * * 1-5`
- Prompt: "Run /vft-fund-tools:scan-comms with Slack scanner only. Scan workspace channels and DMs, classify, and apply updates."

**Full monitor sweep (daily 8am):**
- Task ID: `vft-monitor-sweep`
- Cron: `0 8 * * 1-5`
- Prompt: "Run /vft-fund-tools:monitor to do a full scan of all channels, classify everything, run reactive routing, and produce a morning briefing report."

### Managing Schedules

**Pause a scanner:**
Ask to disable a specific task (e.g., "pause WhatsApp scanning").

**Change frequency:**
Ask to update the cron expression (e.g., "scan email every 2 hours instead of 4").

**Add weekend scanning:**
Change cron day-of-week from `1-5` to `*`.

**Disable all:**
Pause all `vft-*` scheduled tasks.

### Status Check

List all active scheduled tasks and their next run times. Show which scanners are enabled/disabled and when they last ran.

## Arguments

- `setup` — Create all default scheduled tasks
- `status` — Show current schedule and last run times
- `pause <scanner>` — Disable a specific scanner
- `resume <scanner>` — Re-enable a specific scanner
- `frequency <scanner> <hours>` — Change scan interval

## Related Skills

- **comms-hub** — Scanning orchestration
- **email-scanner**, **slack-scanner**, **whatsapp-scanner**, **signal-scanner** — Individual scanners
- **deal-project-classifier** — Classification engine
- **reactive-router** — Reactive dispatch
