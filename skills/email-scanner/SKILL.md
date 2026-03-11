---
name: email-scanner
description: Scan VFT Outlook inbox via Claude in Chrome, extract emails and attachments, save to structured folders, and index in the ingestion database. Use when you need to pull recent emails into the local diligence system for classification.
---

# VFT Email Scanner

Scan the VFT Outlook inbox (https://outlook.cloud.microsoft/mail/) using Claude in Chrome browser automation. Extract emails, download attachments, save everything to `fund/inbox/{YYYY-MM}/{subject-slug}/`, and index metadata in the SQLite ingestion database.

## Prerequisites

- Claude in Chrome extension must be connected
- Outlook must be accessible at https://outlook.cloud.microsoft/mail/ on the bw@vft.institute account
- The ingestion database must exist (`fund/metadata/db/ingestion.db` — run `fund/metadata/init_db.py` if needed)

## Core Workflow

1. **Navigate** to Outlook Web via Claude in Chrome
2. **Scan** inbox for emails within the configured lookback window (default: last 4 hours for cron, configurable for manual runs)
3. **For each email:**
   - Extract: sender, recipients, subject, date, body text
   - Extract sender domain for classification matching
   - Download any attachments
   - Save email body as `email.md` in `fund/inbox/{YYYY-MM}/{subject-slug}/`
   - Save attachments alongside the email.md
4. **Index** each email in the `emails` table of `fund/metadata/db/ingestion.db`
5. **Skip** emails already in the database (dedup on outlook_id or subject+sender+date composite)
6. After scanning, trigger the `deal-project-classifier` skill to classify new emails

## Outlook Web Interaction Patterns

### Reading the Inbox
- Navigate to `https://outlook.cloud.microsoft/mail/`
- The inbox is a list of email previews; use `read_page` to get the accessibility tree
- Click each unread/recent email to open the full view
- Use `get_page_text` to extract the full email body

### Extracting Metadata
From the email detail view, extract:
- **Subject**: heading element at the top of the email
- **Sender**: sender name and email in the header area
- **Recipients**: To/CC fields in the header
- **Date**: timestamp shown in the email header
- **Body**: full text content via `get_page_text`

### Downloading Attachments
- Look for attachment indicators (paperclip icon, attachment section)
- Click each attachment's download button
- Attachments save to the browser's download folder
- Move them to the email's folder in `fund/inbox/`

### Navigating Emails
- Use scroll to load more emails if the lookback window requires it
- Use the search bar for targeted scans (e.g., emails from a specific domain)
- After processing an email, go back to the inbox list

## Email Markdown Format

Each saved email should follow this format:

```markdown
# {Subject}

**From:** {Sender Name} <{sender@domain.com}>
**To:** {recipients}
**Date:** {YYYY-MM-DD HH:MM}
**Attachments:** {list or "None"}

---

{Full email body text}
```

## Folder Structure

```
fund/inbox/
  2026-03/
    midbound-financials-update/
      email.md
      midbound-financials-q4.xlsx
    intro-acme-corp-seed/
      email.md
      acme-deck.pdf
```

## Slug Generation

Subject → slug rules:
- Lowercase, strip non-alphanumeric chars except hyphens
- Collapse multiple hyphens
- Truncate to 60 chars
- If duplicate slug exists in the same month folder, append `-2`, `-3`, etc.

## Database Fields

When inserting into the `emails` table:
- `outlook_id`: Use a composite of `sender + date + subject[:50]` as the dedup key
- `sender_domain`: Extract domain from sender email for classification matching
- `body_preview`: First 500 characters of the body
- `folder_saved_to`: Relative path like `fund/inbox/2026-03/subject-slug/`
- `raw_path`: Absolute path to `email.md`

## Scripts

- `scripts/scan_outlook.py` — Main orchestration (designed to be called by Claude, not run standalone)
  - `--lookback-hours N` — How far back to scan (default: 4)
  - `--max-emails N` — Max emails to process per run (default: 50)
  - `--dry-run` — Preview what would be scanned without saving

## Cron Integration

This skill is called by the `email-scanner-4h` cron every 4 hours Mon–Fri.
The cron invokes this skill with `--lookback-hours 4 --max-emails 50`.

## Error Handling

- If Outlook requires re-authentication, stop and notify the user
- If an attachment fails to download, log the error and continue with the next email
- If the database is locked, retry up to 3 times with 2-second backoff
