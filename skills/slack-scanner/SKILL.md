---
name: slack-scanner
description: Scan VFT Slack workspace via Claude in Chrome (or Slack MCP connector), extract messages from channels and DMs, save to structured folders, and index in the ingestion database. Use when you need to pull recent Slack messages into the local diligence system for classification.
---

# VFT Slack Scanner

Scan the VFT Slack workspace using Claude in Chrome browser automation (with Slack MCP connector as preferred fallback). Extract messages from channels, DMs, and threads, save everything to `fund/inbox/slack/{YYYY-MM}/{channel-slug}/`, and index metadata in the SQLite ingestion database.

## Prerequisites

- Claude in Chrome extension must be connected
- Slack must be accessible at https://app.slack.com/ on the VFT workspace
- The ingestion database must exist (`fund/metadata/db/ingestion.db` -- run `fund/metadata/init_db.py` if needed)

## Connector Strategy

1. **Preferred: Slack MCP connector** -- If a Slack MCP connector is available, use it to list channels, read messages, and fetch threads. This is faster and more reliable than browser automation.
2. **Fallback: Claude in Chrome** -- If no Slack MCP connector is available, use browser automation to navigate to `https://app.slack.com/` and interact with the Slack web UI directly.

## Core Workflow

1. **Check connector availability** -- Search for a Slack MCP connector. If available, use MCP tools. Otherwise, fall back to Claude in Chrome.
2. **Navigate** to Slack Web via Claude in Chrome (if using browser fallback)
3. **Scan** channels and DMs for messages within the configured lookback window (default: last 2 hours for cron, configurable for manual runs)
4. **For each channel/DM with new messages:**
   - Extract: sender, timestamp, channel name, message text
   - If the message has a thread, expand and extract thread replies
   - Download any shared files or attachments
   - Save messages as `messages.md` in `fund/inbox/slack/{YYYY-MM}/{channel-slug}/`
5. **Index** each message in BOTH the legacy `emails` table (if appropriate) AND the unified `messages` table of `fund/metadata/db/ingestion.db`
6. **Skip** messages already in the database (dedup on source + source_id where source_id = workspace|channel|message_ts)
7. After scanning, trigger the `deal-project-classifier` skill to classify new messages

## Slack Web Interaction Patterns (Browser Fallback)

### Reading Channels

- Navigate to `https://app.slack.com/`
- The sidebar shows channels and DMs; use `read_page` to get the accessibility tree
- Click each channel/DM to open the message view
- Use `get_page_text` to extract visible messages

### Extracting Metadata

From the message view, extract:
- **Sender**: username or display name shown next to each message
- **Timestamp**: time shown next to each message (hover for full timestamp)
- **Channel**: channel name from the header or sidebar
- **Body**: message text content
- **Thread**: look for "N replies" links; click to expand thread view

### Expanding Threads

- Click "N replies" or the thread indicator on a message
- The thread panel opens on the right side
- Use `read_page` or `get_page_text` to extract all replies
- Each reply has its own sender and timestamp

### Downloading Attachments

- Look for file attachments (images, PDFs, documents) in messages
- Click the download button or file link
- Attachments save to the browser's download folder
- Move them to the message's folder in `fund/inbox/slack/`

### Navigating Channels

- Use the sidebar channel list to switch between channels
- Use Cmd+K (or Ctrl+K) to quick-switch channels
- Scroll up in a channel to load older messages within the lookback window

## Message Markdown Format

Each saved message batch should follow this format:

```markdown
# #{channel-name} -- {date}

## Messages

### {Sender Name} -- {HH:MM}
{Message text}

### {Sender Name} -- {HH:MM}
{Message text}

#### Thread (N replies)
- **{Reply Sender}** ({HH:MM}): {reply text}
- **{Reply Sender}** ({HH:MM}): {reply text}

---
*Scanned from Slack on {YYYY-MM-DD HH:MM}*
```

## Folder Structure

```
fund/inbox/slack/
  2026-03/
    general/
      messages-2026-03-11.md
    deal-flow/
      messages-2026-03-11.md
    dm-john-doe/
      messages-2026-03-11.md
```

## Slug Generation

Channel/DM name -> slug rules:
- Lowercase, strip non-alphanumeric chars except hyphens
- Prefix DMs with `dm-`
- Collapse multiple hyphens
- Truncate to 60 chars

## Database Fields

When inserting into the unified `messages` table:
- `source`: `"slack"`
- `source_id`: Composite of `{workspace}|{channel_id}|{message_ts}`
- `type`: `"message"` for individual messages, `"thread"` for thread parents with replies
- `sender`: Display name of the message sender
- `recipients`: JSON array (channel members or DM participants)
- `subject`: Channel name or DM participant names
- `body`: Full message text (including thread replies for thread type)
- `timestamp`: ISO-8601 timestamp of the message
- `channel`: Channel name (e.g., `#general`, `#deal-flow`, `DM: John Doe`)
- `attachments`: JSON array of `{name, path}` objects
- `raw_path`: Absolute path to the saved `messages-{date}.md` file
- `metadata`: JSON with Slack-specific extras (workspace, channel_id, message_ts, thread_ts, permalink)

## Scripts

- `scripts/scan_slack.py` -- Main orchestration (designed to be called by Claude, not run standalone)
  - `--lookback-hours N` -- How far back to scan (default: 2)
  - `--max-messages N` -- Max messages to process per run (default: 200)
  - `--channels` -- Comma-separated channel names to scan (default: all recent)
  - `--dry-run` -- Preview what would be scanned without saving

## Cron Integration

This skill is called by the `slack-scanner-2h` cron every 2 hours Mon--Fri.
The cron invokes this skill with `--lookback-hours 2 --max-messages 200`.

## Error Handling

- If Slack requires re-authentication, stop and notify the user
- If a thread fails to expand, log the error and continue with the next message
- If the database is locked, retry up to 3 times with 2-second backoff
- If the Slack MCP connector is unavailable, fall back to browser automation
