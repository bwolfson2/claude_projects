---
name: whatsapp-scanner
description: Scan WhatsApp Web via Claude in Chrome, extract messages from configured groups and contacts, save to structured folders, and index in the unified messages table. Use when you need to pull recent WhatsApp messages into the local diligence system for classification.
---

# VFT WhatsApp Scanner

Scan WhatsApp Web (https://web.whatsapp.com/) using Claude in Chrome browser automation. Extract messages from configured groups and contacts, save to `fund/inbox/whatsapp/{YYYY-MM}/{contact-or-group-slug}/`, and index metadata in the SQLite ingestion database (unified `messages` table).

## Prerequisites

- Claude in Chrome extension must be connected
- WhatsApp Web must be accessible at https://web.whatsapp.com/ with an active session (QR code already scanned)
- The ingestion database must exist (`fund/metadata/db/ingestion.db` — run `fund/metadata/init_db.py` if needed)

## Configured Targets

The scan targets (groups and contacts) are defined in the `SCAN_TARGETS` dict inside `scripts/scan_whatsapp.py`. Update that dict to add or remove groups/contacts to monitor.

## Core Workflow

1. **Navigate** to WhatsApp Web via Claude in Chrome
2. **Verify** the session is active (not showing QR code screen)
3. **For each configured group/contact:**
   - Search for and open the chat
   - Extract messages within the lookback window (default: last 4 hours for cron, configurable for manual runs)
4. **For each message:**
   - Extract: sender name, message text, timestamp
   - Determine the group or contact name as the channel
   - Skip messages already in the database (dedup on source_id)
   - Save message to filesystem as `messages.md` (appended per chat)
5. **Index** each message in the unified `messages` table of `fund/metadata/db/ingestion.db`
6. **Skip** messages already in the database (dedup on composite source_id)
7. After scanning, trigger the `deal-project-classifier` skill to classify new messages

## WhatsApp Web Interaction Patterns

### Verifying Active Session
- Navigate to `https://web.whatsapp.com/`
- Use `read_page` to check for the chat list panel
- If a QR code screen is shown, stop and notify the user that WhatsApp Web needs re-authentication

### Searching for a Chat
- Use the search bar at the top of the chat list
- Type the group or contact name
- Use `read_page` to find the matching result
- Click the result to open the chat

### Reading Messages
- Once a chat is open, use `read_page` to get the accessibility tree of the message list
- Messages appear as list items with sender name, text content, and timestamp
- Use `get_page_text` for longer message content if needed
- Scroll up to load older messages if within the lookback window

### Extracting Metadata
From each message element, extract:
- **Sender**: The name shown above the message (in groups) or the contact name (in DMs)
- **Text**: The message body content
- **Timestamp**: Time shown on the message (combine with today's date or the date separator)
- **Group/Contact**: The chat name shown in the header

### Handling Date Separators
- WhatsApp shows date separator elements (e.g., "TODAY", "YESTERDAY", "3/10/2026")
- Track the current date context from these separators to build full timestamps
- Default to today's date if no separator is visible

### Navigating Between Chats
- After processing one chat, click the back arrow or use the search bar to find the next target
- Wait briefly for the chat to load before reading messages

## Message Markdown Format

Each chat's messages are saved as a single `messages.md` file:

```markdown
# {Group or Contact Name}

**Scanned:** {YYYY-MM-DD HH:MM}
**Source:** WhatsApp Web

---

### {Sender Name} — {YYYY-MM-DD HH:MM}
{Message text}

### {Sender Name} — {YYYY-MM-DD HH:MM}
{Message text}

...
```

## Folder Structure

```
fund/inbox/whatsapp/
  2026-03/
    vft-deal-flow/
      messages.md
    john-doe/
      messages.md
    founders-group/
      messages.md
```

## Slug Generation

Group/Contact name to slug rules:
- Lowercase, strip non-alphanumeric chars except hyphens
- Collapse multiple hyphens
- Truncate to 60 chars

## Database Fields

When inserting into the unified `messages` table:
- `source`: `"whatsapp"`
- `source_id`: Composite of `{group_or_contact_slug}|{sender}|{timestamp}` as the dedup key
- `type`: `"message"`
- `sender`: Sender name as shown in WhatsApp
- `recipients`: JSON array — `[]` for group messages, `[contact_name]` for DMs
- `subject`: `null` (WhatsApp messages don't have subjects)
- `body`: Full message text
- `timestamp`: ISO-8601 formatted timestamp
- `channel`: Group name or contact name
- `attachments`: `"[]"` (attachment download not supported in initial version)
- `raw_path`: Absolute path to the `messages.md` file
- `metadata`: JSON with `{"chat_type": "group"|"direct"}`

## Scripts

- `scripts/scan_whatsapp.py` — Main orchestration (designed to be called by Claude, not run standalone)
  - `--lookback-hours N` — How far back to scan (default: 4)
  - `--max-messages N` — Max messages to process per run (default: 200)
  - `--status` — Show scan status

## Cron Integration

This skill is called by the `whatsapp-scanner-4h` cron every 4 hours Mon-Fri.
The cron invokes this skill with `--lookback-hours 4 --max-messages 200`.

## Error Handling

- If WhatsApp Web requires QR code re-authentication, stop and notify the user
- If a chat cannot be found in the search results, log a warning and skip to the next target
- If no new messages are found in a chat, continue silently (no errors, no phantom entries)
- If the database is locked, retry up to 3 times with 2-second backoff
