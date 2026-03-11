# Signal Scanner Cron Configuration

## Task: signal-scanner-4h

**Schedule:** Every 4 hours, Mon-Fri (business hours)
**Cron expression:** `0 9,13,17,21 * * 1-5`
**Task name:** `signal-scanner-4h`

### Prompt for Scheduled Task

```
Scan Signal messages and ingest them into the diligence system.

Steps:
1. Read the skill file at skills/signal-scanner/SKILL.md for full workflow details.
2. Read the scan_signal.py helper at skills/signal-scanner/scripts/scan_signal.py.
3. Run `python skills/signal-scanner/scripts/scan_signal.py --check-cli` to detect if signal-cli is available.
4. Run `python skills/signal-scanner/scripts/scan_signal.py --status` to check current state.
5. If signal-cli is available: use signal-cli to receive and parse messages.
6. If signal-cli is unavailable: use Claude in Chrome to open Signal Desktop and scan conversations.
7. For each message: extract sender, timestamp, group/contact name, and body text.
8. For each message with attachments: download or copy attachments.
9. Call the save_message() function from scan_signal.py for each message to save to fund/inbox/signal/{YYYY-MM}/{contact-or-group-slug}/ and index in the SQLite database.
10. After scanning, run the classifier: `python skills/deal-project-classifier/scripts/classify_batch.py`
11. Then apply updates: `python skills/deal-project-classifier/scripts/apply_updates.py`

Success criteria: New Signal messages saved to fund/inbox/signal/, indexed in fund/metadata/db/ingestion.db, and classified.
Working directory: The due_diligences folder synced via Google Drive for Desktop.
```
