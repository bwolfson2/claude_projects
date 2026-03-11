# WhatsApp Scanner Cron Configuration

## Task: whatsapp-scanner-4h

**Schedule:** Every 4 hours, Mon-Fri (business hours)
**Cron expression:** `0 9,13,17,21 * * 1-5`
**Task name:** `whatsapp-scanner-4h`

### Prompt for Scheduled Task

```
Scan configured WhatsApp groups and contacts for recent messages and ingest them into the diligence system.

Steps:
1. Read the skill file at skills/whatsapp-scanner/SKILL.md for full workflow details.
2. Read the scan_whatsapp.py helper at skills/whatsapp-scanner/scripts/scan_whatsapp.py.
3. Run `python skills/whatsapp-scanner/scripts/scan_whatsapp.py --status` to check current state.
4. Use Claude in Chrome to navigate to https://web.whatsapp.com/ and verify the session is active.
5. For each configured target in SCAN_TARGETS, open the chat and scan the last 4 hours of messages.
6. For each message: extract sender, text, and timestamp.
7. Call save_message() from scan_whatsapp.py for each new message to save to fund/inbox/whatsapp/{YYYY-MM}/{chat-slug}/ and index in the unified messages table.
8. After scanning, run the classifier: `python skills/deal-project-classifier/scripts/classify_batch.py`
9. Then apply updates: `python skills/deal-project-classifier/scripts/apply_updates.py`

Success criteria: New messages saved to fund/inbox/whatsapp/, indexed in fund/metadata/db/ingestion.db messages table, and classified.
Working directory: The due_diligences folder synced via Google Drive for Desktop.
```
