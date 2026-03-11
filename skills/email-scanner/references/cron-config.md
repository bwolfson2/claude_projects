# Email Scanner Cron Configuration

## Task: email-scanner-4h

**Schedule:** Every 4 hours, Mon–Fri (business hours)
**Cron expression:** `0 9,13,17,21 * * 1-5`
**Task name:** `email-scanner-4h`

### Prompt for Scheduled Task

```
Scan the VFT Outlook inbox for recent emails and ingest them into the diligence system.

Steps:
1. Read the skill file at skills/email-scanner/SKILL.md for full workflow details.
2. Read the scan_outlook.py helper at skills/email-scanner/scripts/scan_outlook.py.
3. Run `python skills/email-scanner/scripts/scan_outlook.py --status` to check current state.
4. Use Claude in Chrome to navigate to https://outlook.cloud.microsoft/mail/ on the bw@vft.institute account.
5. Scan the last 4 hours of emails in the inbox.
6. For each email: extract subject, sender, recipients, date, and body text.
7. For each email with attachments: download attachments.
8. Call the save_email() function from scan_outlook.py for each email to save to fund/inbox/{YYYY-MM}/{subject-slug}/ and index in the SQLite database.
9. After scanning, run the classifier: `python skills/deal-project-classifier/scripts/classify_batch.py`
10. Then apply updates: `python skills/deal-project-classifier/scripts/apply_updates.py`

Success criteria: New emails saved to fund/inbox/, indexed in fund/metadata/db/ingestion.db, and classified.
Working directory: The due_diligences folder synced via Google Drive for Desktop.
```
