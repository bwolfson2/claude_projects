---
description: Add or update a contact in the CRM
argument-hint: "<name> [email] [details...]"
---

# Add Contact

Add a new contact or update an existing one in the fund CRM.

## Arguments

`$ARGUMENTS`

Parse the arguments to extract:
- **Name** (required) — full name of the contact
- **Email** — if provided, used as the dedup key
- **Details** — any of: company, title/role, phone, Slack handle, LinkedIn URL, tags, context notes

## Steps

1. **Parse input** — Extract structured fields from the free-text arguments:
   - Look for email patterns (`user@domain.com`)
   - Look for "at" or "@" followed by a company name
   - Look for titles/roles: "founder", "CEO", "partner", "VP", "investor", etc.
   - Look for phone numbers (digits with optional +, -, spaces)
   - Look for LinkedIn URLs
   - Look for Slack handles (`@handle`)
   - Look for tag keywords: founder, investor, advisor, candidate, lp, board, legal

2. **Check for existing contact** by email in the database:
   ```bash
   sqlite3 fund/metadata/db/ingestion.db "SELECT * FROM contacts WHERE email = '<email>'"
   ```

3. **If existing** — update with any new fields provided (don't overwrite existing non-null values unless explicitly asked)

4. **If new** — insert into the contacts table:
   ```bash
   sqlite3 fund/metadata/db/ingestion.db "INSERT INTO contacts (name, email, company, title, phone, slack_handle, linkedin_url, tags, source, first_seen, last_contacted) VALUES (...)"
   ```

5. **Link to deals/projects** — if company matches an existing deal or project, auto-link:
   ```bash
   sqlite3 fund/metadata/db/ingestion.db "SELECT slug FROM deals WHERE company_name LIKE '%<company>%'"
   ```

6. **Optional enrichment** — if `--enrich` flag or user requests:
   - Web search for LinkedIn profile
   - Extract title from LinkedIn if found
   - Match company to existing deals

7. **Export updated contacts**:
   ```bash
   python skills/crm-contacts/scripts/sync_contacts.py
   ```

8. **Report** — confirm the contact was added/updated with all extracted fields

## Examples

```
/vft-fund-tools:add-contact Jane Smith jane@startup.com founder at WidgetCo
/vft-fund-tools:add-contact "Bob Jones" bob@vc.fund partner +1-555-0123
/vft-fund-tools:add-contact Alice Chen @alice-chen investor context:"Met at demo day"
/vft-fund-tools:add-contact --merge jane@startup.com jane@personal.com
```

## Merge Mode

With `--merge`, provide two emails to merge contacts:
```
/vft-fund-tools:add-contact --merge email1@a.com email2@b.com
```
This merges the second contact into the first, preserving all non-null fields from both.
