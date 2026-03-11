---
name: signal-scanner
description: Scan Signal messages via signal-cli or Chrome on Signal Desktop, extract messages with metadata, save to structured folders, and index in the ingestion database. Use when you need to pull recent Signal messages into the local diligence system for classification.
---

# VFT Signal Scanner

Scan Signal messages and ingest them into the diligence system. Supports two modes: **signal-cli** (preferred, headless) or **Chrome on Signal Desktop** (fallback, browser automation). Extract messages, save to `fund/inbox/signal/{YYYY-MM}/{contact-or-group-slug}/`, and index metadata in the SQLite ingestion database.

## Prerequisites

- **signal-cli mode:** `signal-cli` must be installed and registered with the VFT phone number
- **Chrome mode:** Claude in Chrome extension must be connected, Signal Desktop must be open at `signal://` or the Signal Web interface
- The ingestion database must exist (`fund/metadata/db/ingestion.db` — run `fund/metadata/init_db.py` if needed)

## Mode Selection

1. **Check signal-cli first** — run `scripts/scan_signal.py --check-cli` or call `check_signal_cli()` from the helper
2. If signal-cli is available and registered, use signal-cli mode
3. If signal-cli is unavailable, fall back to Chrome on Signal Desktop mode
4. Log which mode is active at the start of every scan

## Core Workflow

1. **Detect mode** — check for signal-cli availability, fall back to Chrome
2. **Scan** messages within the configured lookback window (default: last 4 hours for cron, configurable for manual runs)
3. **For each message:**
   - Extract: sender, timestamp, group or contact name, message body
   - Determine channel (group name or contact name)
   - Save message as `message.md` in `fund/inbox/signal/{YYYY-MM}/{contact-or-group-slug}/`
   - Save any attached media alongside the message.md
4. **Index** each message in the `messages` table of `fund/metadata/db/ingestion.db`
5. **Skip** messages already in the database (dedup on source_id = sender + timestamp composite)
6. After scanning, trigger the `deal-project-classifier` skill to classify new messages

## signal-cli Mode

### Reading Messages
- Run `signal-cli -u <number> receive --json` to pull pending messages
- Parse JSON output line by line
- Each line is a JSON object with envelope containing source, timestamp, dataMessage

### Extracting Metadata
From the signal-cli JSON output, extract:
- **Sender**: `envelope.source` (phone number or profile name)
- **Timestamp**: `envelope.timestamp` (epoch ms, convert to ISO)
- **Group**: `envelope.dataMessage.groupInfo.groupId` if present
- **Body**: `envelope.dataMessage.message`
- **Attachments**: `envelope.dataMessage.attachments[]` if present

### Group Name Resolution
- signal-cli stores group info locally; use `signal-cli -u <number> listGroups` to map groupId to group name
- Cache group names for the duration of the scan

## Chrome on Signal Desktop Mode

### Reading Messages
- Use `read_page` to get the accessibility tree of Signal Desktop
- The conversation list is in the left panel; recent messages appear at the top
- Click each conversation to open the message thread
- Use `get_page_text` to extract message content

### Extracting Metadata
From the Signal Desktop view, extract:
- **Sender**: contact name or phone number from the message header
- **Timestamp**: time shown on each message bubble
- **Group**: group name from the conversation header (if group chat)
- **Body**: full text content of each message
- **Attachments**: look for media/file indicators in the message

### Navigating Conversations
- Use scroll to load older messages if the lookback window requires it
- After processing a conversation, go back to the conversation list
- Continue until all conversations with recent activity are processed

## Message Markdown Format

Each saved message should follow this format:

```markdown
# Signal: {Group or Contact Name}

**From:** {Sender}
**Channel:** {Group Name or Contact Name}
**Date:** {YYYY-MM-DD HH:MM}
**Attachments:** {list or "None"}

---

{Full message body text}
```

## Folder Structure

```
fund/inbox/signal/
  2026-03/
    vft-deal-team/
      message.md
      photo-2026-03-11.jpg
    john-doe/
      message.md
```

## Slug Generation

Channel name (group or contact) to slug rules:
- Lowercase, strip non-alphanumeric chars except hyphens
- Collapse multiple hyphens
- Truncate to 60 chars
- If duplicate slug exists in the same month folder, append `-2`, `-3`, etc.

## Database Fields

When inserting into the `messages` table:
- `source`: `"signal"`
- `type`: `"message"`
- `source_id`: Composite of `sender + "|" + timestamp` as the dedup key
- `channel`: Group name or contact name
- `sender`: Sender phone number or profile name
- `body_preview`: First 500 characters of the body
- `folder_saved_to`: Relative path like `fund/inbox/signal/2026-03/vft-deal-team/`
- `raw_path`: Absolute path to `message.md`

## Scripts

- `scripts/scan_signal.py` — Main orchestration (designed to be called by Claude, not run standalone)
  - `--lookback-hours N` — How far back to scan (default: 4)
  - `--max-messages N` — Max messages to process per run (default: 100)
  - `--check-cli` — Check if signal-cli is installed and registered
  - `--status` — Show scan status
  - `--dry-run` — Preview what would be scanned without saving

## Cron Integration

This skill is called by the `signal-scanner-4h` cron every 4 hours Mon-Fri.
The cron invokes this skill with `--lookback-hours 4 --max-messages 100`.

## Error Handling

- If signal-cli is not installed, fall back to Chrome mode gracefully
- If signal-cli is installed but not registered, stop and notify the user
- If Signal Desktop requires re-authentication, stop and notify the user
- If an attachment fails to download, log the error and continue with the next message
- If the database is locked, retry up to 3 times with 2-second backoff
