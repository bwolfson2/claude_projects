# Transcript Ingestion Cron Configuration

## Task: transcript-ingest-daily

**Schedule:** Daily at 9am
**Cron expression:** `0 9 * * *`
**Task name:** `transcript-ingest-daily`

### Prompt for Scheduled Task

```
Ingest new meeting transcripts from Granola into the VFT diligence system.

Steps:
1. Read the skill file at skills/transcript-ingestion/SKILL.md for full workflow details.
2. Read the ingest_transcripts.py helper at skills/transcript-ingestion/scripts/ingest_transcripts.py.
3. Run `python skills/transcript-ingestion/scripts/ingest_transcripts.py --status` to check current state.
4. Use the Granola MCP connector tools (list_meetings, get_meeting_transcript) to list meetings from the last 24 hours.
5. For each new meeting not already in the database:
   a. Fetch the full transcript via get_meeting_transcript.
   b. Extract title, participants, date, summary, and action items.
   c. Call save_transcript() from ingest_transcripts.py to save to fund/transcripts/{YYYY-MM}/ and index in SQLite.
6. After ingestion, run the classifier: `python skills/deal-project-classifier/scripts/classify_batch.py`
7. Then apply updates: `python skills/deal-project-classifier/scripts/apply_updates.py`

Success criteria: New transcripts saved to fund/transcripts/, indexed in fund/metadata/db/ingestion.db, and classified.
Working directory: The due_diligences folder synced via Google Drive for Desktop.
```
