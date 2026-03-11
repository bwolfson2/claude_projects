# Slack Scanner Cron Configuration

## Task: slack-scanner-2h

**Schedule:** Every 2 hours, Mon--Fri (business hours)
**Cron expression:** `0 9,11,13,15,17,19 * * 1-5`
**Task name:** `slack-scanner-2h`

### Prompt for Scheduled Task

```
Scan the VFT Slack workspace for recent messages and ingest them into the diligence system.

Steps:
1. Read the skill file at skills/slack-scanner/SKILL.md for full workflow details.
2. Read the scan_slack.py helper at skills/slack-scanner/scripts/scan_slack.py.
3. Run `python skills/slack-scanner/scripts/scan_slack.py --status` to check current state.
4. Check if a Slack MCP connector is available. If so, use MCP tools. Otherwise, use Claude in Chrome to navigate to https://app.slack.com/ on the VFT workspace.
5. Scan the last 2 hours of messages across active channels and DMs.
6. For each message: extract sender, timestamp, channel, and body text.
7. For threads: expand and extract all replies.
8. For messages with attachments: download files.
9. Call the save_message() function from scan_slack.py for each message to save to fund/inbox/slack/{YYYY-MM}/{channel-slug}/ and index in the SQLite database.
10. After scanning, run the classifier: `python skills/deal-project-classifier/scripts/classify_batch.py`
11. Then apply updates: `python skills/deal-project-classifier/scripts/apply_updates.py`

Success criteria: New messages saved to fund/inbox/slack/, indexed in fund/metadata/db/ingestion.db (unified messages table), and classified.
Working directory: The due_diligences folder synced via Google Drive for Desktop.
```
