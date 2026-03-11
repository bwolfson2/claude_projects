---
name: message-ingestion
description: Ingest messages from any communication source (Outlook, Slack, WhatsApp, Signal, Granola, web scrapes) into the unified messages table. Use when a scanner or connector needs to store a message in the ingestion database with normalized schema, dedup, and multi-project tagging.
---

# Message Ingestion

Provide a unified ingestion interface for all communication sources. Every scanner and connector writes through this skill to ensure consistent schema, dedup, and project tagging.

## Core Workflow

1. Accept a message payload matching the unified message schema.
2. Validate required fields (source, source_id, type, timestamp).
3. Check for duplicates using the (source, source_id) composite key.
4. Insert into the `messages` table in `fund/metadata/db/ingestion.db`.
5. Return the message ID for downstream processing.

## Unified Message Schema

Every message must conform to:

```json
{
  "source": "outlook|slack|whatsapp|signal|granola|web",
  "source_id": "unique-id-from-source",
  "type": "email|message|transcript|thread|document|scrape",
  "sender": "name <email-or-phone>",
  "recipients": ["recipient1", "recipient2"],
  "subject": "optional subject line",
  "body": "text content",
  "timestamp": "ISO-8601",
  "channel": "inbox|#channel|group-name|direct|url",
  "attachments": [{"name": "file.pdf", "path": "/local/path"}],
  "project_tags": ["slug1", "slug2"],
  "raw_path": "/absolute/path/to/saved/file",
  "metadata": {}
}
```

Note: `project_tags` is an array — a single message can be tagged to multiple projects.

## Scripts

- `scripts/ingest_message.py` — Insert or update a single message
  - `--source outlook` — Source platform
  - `--source-id <id>` — Dedup key from the source
  - `--type email` — Message type
  - `--payload <json>` — Full message payload as JSON string
  - `--dry-run` — Preview without inserting

## Migration

If the database is at schema v1 (separate emails/transcripts tables), run:
```
python fund/metadata/migrate_v2_unified_messages.py
```

This migrates existing emails and transcripts into the unified messages table while preserving all data and the original tables for backward compatibility.

## Dedup Rules

- Primary dedup: UNIQUE(source, source_id) constraint
- If a message with the same source + source_id exists, the insert is skipped (INSERT OR IGNORE)
- Scanners are responsible for generating stable source_ids from their platform

## Working Rules

- Always validate the source is one of: outlook, slack, whatsapp, signal, granola, web
- Always validate the type is one of: email, message, transcript, thread, document, scrape
- Store recipients and attachments as JSON arrays
- Store project_tags as JSON array (empty `[]` if unclassified)
- Store metadata as JSON object for source-specific fields
- Preserve raw_path as absolute path to the saved markdown/file
