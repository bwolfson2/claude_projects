---
name: transcript-ingestion
description: Pull meeting transcripts from the Granola MCP connector, save them locally as markdown, and index in the VFT ingestion database for classification. Use when you need to ingest recent meeting transcripts into the diligence system.
---

# VFT Transcript Ingestion

Pull meeting transcripts from the Granola MCP connector (already connected), save them as structured markdown in `fund/transcripts/{YYYY-MM}/`, and index metadata in the SQLite ingestion database.

## Prerequisites

- Granola MCP connector must be connected (tools: `query_granola`, `list_meetings`, `get_meetings`, `get_meeting_transcript`)
- The ingestion database must exist (`fund/metadata/db/ingestion.db` — run `fund/metadata/init_db.py` if needed)

## Core Workflow

1. **List recent meetings** using `list_meetings` or `get_meetings` from the Granola connector
2. **Filter** to meetings not yet in the database (dedup on granola_id)
3. **For each new meeting:**
   - Fetch the full transcript via `get_meeting_transcript`
   - Extract: title, participants, date, summary/notes
   - Save as markdown to `fund/transcripts/{YYYY-MM}/{meeting-slug}.md`
   - Insert metadata into the `transcripts` table
4. After ingestion, trigger the `deal-project-classifier` skill to classify new transcripts

## Granola MCP Tools

### list_meetings / get_meetings
- Returns a list of meetings with metadata (id, title, date, participants)
- Use date filters to get only recent meetings since last ingestion

### get_meeting_transcript
- Takes a meeting ID
- Returns the full transcript text with speaker labels
- May also return summary and action items

### query_granola
- Natural language query across all meetings
- Useful for targeted searches (e.g., "meetings with Midbound")

## Transcript Markdown Format

```markdown
# {Meeting Title}

**Date:** {YYYY-MM-DD HH:MM}
**Participants:** {Comma-separated names}
**Duration:** {if available}
**Granola ID:** {id}

## Summary

{Meeting summary or key points if available}

## Action Items

{Extracted action items if available}

## Transcript

{Full transcript with speaker labels}

---
*Ingested from Granola on {ingestion date}*
```

## Folder Structure

```
fund/transcripts/
  2026-03/
    midbound-founder-call-0305.md
    portfolio-ops-sync-0308.md
    lp-quarterly-update-0310.md
```

## Slug Generation

Meeting title → slug rules:
- Lowercase, strip non-alphanumeric chars except hyphens
- Append date as `-MMDD` suffix
- Truncate to 60 chars
- Deduplicate with `-2`, `-3` suffix if needed

## Database Fields

When inserting into the `transcripts` table:
- `granola_id`: The unique meeting ID from Granola (primary dedup key)
- `title`: Meeting title
- `participants`: Comma-separated participant names/emails
- `date`: Meeting date in ISO-8601 format
- `summary`: First 500 chars of summary or transcript
- `raw_path`: Absolute path to saved markdown file

## Scripts

- `scripts/ingest_transcripts.py` — Main orchestration
  - `--since YYYY-MM-DD` — Only ingest meetings after this date (default: last 24 hours)
  - `--max-meetings N` — Max meetings to process per run (default: 20)
  - `--dry-run` — Preview what would be ingested without saving

## Cron Integration

This skill is called by the `transcript-ingest-daily` cron every day at 9am.
The cron invokes this skill with default settings (last 24 hours, max 20 meetings).

## Error Handling

- If the Granola connector is not available, log the error and exit cleanly
- If a transcript fetch fails, skip it and continue with the next meeting
- If the database is locked, retry up to 3 times with 2-second backoff
- If saving a transcript fails due to filesystem issues, log and continue

## Participant Extraction

Participant names/emails are critical for classification. When extracting:
- Prefer email addresses over display names (better for domain matching)
- Store both the raw participant list and extracted emails separately if possible
- Common patterns: "John Doe (john@company.com)" → extract both name and email
