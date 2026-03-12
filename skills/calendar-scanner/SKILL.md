---
name: calendar-scanner
description: Scan calendar events via Google Calendar MCP, Microsoft 365 MCP, or Claude in Chrome fallback. Extract upcoming and recent meetings, save to structured folders, and index in the ingestion database for deal/project matching. Use when you need to pull calendar events into the local diligence system.
---

# VFT Calendar Scanner

Scan calendar events using a Google Calendar MCP connector (preferred), Microsoft 365 MCP connector (alternative), or Claude in Chrome browser automation (fallback). Extract events, save to `fund/inbox/calendar/{YYYY-MM}/events-{YYYY-MM-DD}.md`, and index metadata in the SQLite ingestion database (unified `messages` table).

## Prerequisites

- At least one calendar connector configured in `.mcp.json` (Google Calendar or ms365), OR Claude in Chrome extension connected
- The ingestion database must exist (`fund/metadata/db/ingestion.db` -- run `fund/metadata/init_db.py` if needed)

## Connector Strategy

1. **Preferred: Google Calendar MCP** -- If the `google-calendar` MCP connector is available, use it to list events, read event details, and get attendee information. This is the fastest and most reliable option.
2. **Alternative: Microsoft 365 MCP** -- If Google Calendar is unavailable but `ms365` MCP connector is available, use it to access Outlook Calendar events. Supports the same workflow.
3. **Fallback: Claude in Chrome** -- If no calendar MCP connector is available, use browser automation to navigate to `https://calendar.google.com/` or `https://outlook.cloud.microsoft/calendar/` and extract events visually.

## Core Workflow

1. **Check connector availability** -- Search for Google Calendar MCP connector first. If unavailable, try ms365 MCP. If neither available, fall back to Claude in Chrome.
2. **List events** -- Query events in the configured window (default: 1 day back + 7 days forward)
3. **For each event:**
   - Extract: title, organizer, attendees, start/end time, location, description, conference URL
   - Build source_id for dedup: `{calendar_id}|{event_id}`
   - Check if already scanned (skip if duplicate)
   - Save event to markdown file
4. **Extract attendee domains** -- Parse attendee email addresses to extract domains for deal/project matching
5. **Index** each event in the unified `messages` table with `source = "calendar"`, `type = "event"`
6. **Skip** events already in the database (dedup on source + source_id)
7. After scanning, trigger the `deal-project-classifier` skill to match events to deals/projects

## Calendar Interaction Patterns (Browser Fallback)

### Google Calendar
- Navigate to `https://calendar.google.com/`
- Switch to "Schedule" or "List" view for easier extraction
- Use `read_page` to get the accessibility tree of events
- Click each event to open the detail popup
- Extract title, time, attendees, location, and description

### Outlook Calendar
- Navigate to `https://outlook.cloud.microsoft/calendar/`
- Switch to "List" or "Agenda" view
- Use `read_page` to get event listings
- Click each event for full details
- Extract same metadata as above

### Navigating Date Ranges
- Use date navigation (arrows, date picker) to move through the lookback window
- For forward-looking events, navigate day by day through the next 7 days
- For past events, navigate back 1 day to capture yesterday's meetings

## Event Markdown Format

Events are saved as daily files, appending each event:

```markdown
# Calendar Events -- {YYYY-MM-DD}

### {Event Title} -- {HH:MM}--{HH:MM}
**Organizer:** {Organizer Name} <{email}>
**Attendees:** {Name1}, {Name2}, {Name3}
**Location:** {Physical location or video link}
**Status:** {confirmed | tentative | cancelled}

{Event description text}

---
```

## Folder Structure

```
fund/inbox/calendar/
  2026-03/
    events-2026-03-11.md
    events-2026-03-12.md
    events-2026-03-13.md
```

## Database Fields

When inserting into the unified `messages` table:
- `source`: `"calendar"`
- `source_id`: `"{calendar_id}|{event_id}"` as the dedup key
- `type`: `"event"`
- `sender`: Organizer name and email
- `recipients`: JSON array of attendee emails
- `subject`: Event title
- `body`: Event description + formatted attendee list
- `timestamp`: Event start time in ISO-8601 format
- `channel`: Calendar name (e.g., "primary", "Work", "VFT Calendar")
- `attachments`: `"[]"` (calendar events typically have no file attachments)
- `raw_path`: Absolute path to the `events-{date}.md` file
- `metadata`: JSON with calendar-specific extras:
  ```json
  {
    "calendar_id": "primary",
    "event_id": "abc123",
    "start": "2026-03-12T10:00:00-08:00",
    "end": "2026-03-12T11:00:00-08:00",
    "location": "Zoom",
    "conference_url": "https://zoom.us/j/123456",
    "attendees": [
      {"name": "Jane Doe", "email": "jane@acme.com", "status": "accepted"},
      {"name": "Bob Smith", "email": "bob@vft.institute", "status": "accepted"}
    ],
    "recurrence": null,
    "status": "confirmed",
    "attendee_domains": ["acme.com", "vft.institute"]
  }
  ```

## Scripts

- `scripts/scan_calendar.py` -- Main orchestration (designed to be called by Claude, not run standalone)
  - `--lookback-days N` -- How many days forward to scan (default: 7)
  - `--past-days N` -- How many days back to scan (default: 1)
  - `--max-events N` -- Max events to process per run (default: 100)
  - `--calendar google|outlook|all` -- Which calendar provider to scan (default: all)
  - `--status` -- Show scan status

## Cron Integration

This skill is called by the `calendar-scanner-daily` cron every day at 7:00 AM Mon-Fri.
The cron invokes this skill with `--lookback-days 7 --past-days 1 --max-events 100`.

## Error Handling

- If the Google Calendar MCP connector is unavailable, try Microsoft 365 MCP
- If no MCP connector is available, fall back to browser automation
- If the calendar requires re-authentication, stop and notify the user
- If an event cannot be parsed, log the error and continue with the next event
- If the database is locked, retry up to 3 times with 2-second backoff
