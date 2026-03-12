---
name: crm-contacts
description: Manage a unified contact CRM across all communication platforms — extract contacts from emails, Slack, WhatsApp, Signal, and meeting transcripts. Deduplicate, merge cross-platform identities, and maintain relationship context. Use when you need to find contacts, add new ones, or understand who the fund knows at a company.
---

# CRM Contacts

Unified contact management across all fund communication channels. Automatically extracts contacts from ingested messages, deduplicates across platforms, and maintains relationship context.

## Data Model

Each contact record includes:
- **Identity:** name, email, phone, company, title
- **Platform handles:** Slack, WhatsApp, Signal, LinkedIn
- **Relationships:** linked deals, linked projects, tags (founder/investor/advisor/candidate)
- **Activity:** first seen, last contacted, source platform
- **Context:** free-text relationship notes

Contacts stored in `contacts` table (ingestion.db) and exported to `fund/crm/contacts.json`.

## Scripts

### Extract contacts from messages
```bash
python skills/crm-contacts/scripts/extract_contacts.py
```
Scans all messages in ingestion.db, extracts unique sender/recipient pairs, deduplicates by email, links to deals/projects via classification_log.

### Merge cross-platform identities
```bash
python skills/crm-contacts/scripts/merge_contacts.py
```
Finds the same person across platforms (email ↔ Slack handle ↔ WhatsApp phone), merges records.

### Export contacts to JSON
```bash
python skills/crm-contacts/scripts/sync_contacts.py
```
Exports contacts table → `fund/crm/contacts.json` for sheet-sync.

## Workflows

### Auto-extraction (runs after /monitor or /scan-comms)
1. New messages scanned → contacts extracted automatically
2. Email sender/recipients → name + email + company (from domain)
3. Slack messages → name + Slack handle
4. WhatsApp/Signal → name + phone number
5. Meeting transcripts → participant names

### Manual addition
```
/vft-fund-tools:add-contact Jane Smith jane@startup.com founder at WidgetCo
```

### Enrichment
When a contact is added, optionally:
- Web search for LinkedIn profile
- Match to existing deal/project by company domain
- Pull title from email signature patterns
