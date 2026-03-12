# Contact Schema Reference

## Fields

| Field | Type | Description |
|-------|------|-------------|
| name | TEXT | Full name |
| email | TEXT (UNIQUE) | Primary email — dedup key |
| phone | TEXT | Phone number (with country code) |
| company | TEXT | Company name (auto-extracted from email domain) |
| title | TEXT | Role/title (from email signatures, LinkedIn) |
| slack_handle | TEXT | Slack @handle |
| whatsapp_id | TEXT | WhatsApp phone/ID |
| signal_id | TEXT | Signal phone/ID |
| linkedin_url | TEXT | LinkedIn profile URL |
| tags | JSON | Array of tags: founder, investor, advisor, candidate, lp, board, legal, etc. |
| context | TEXT | Free-text relationship notes |
| deal_slugs | JSON | Array of linked deal slugs |
| project_slugs | JSON | Array of linked project slugs |
| first_seen | TEXT | ISO timestamp — when first encountered |
| last_contacted | TEXT | ISO timestamp — most recent interaction |
| source | TEXT | Platform first seen on (outlook, slack, whatsapp, signal, granola, manual) |

## Auto-Extraction Rules

| Source | Name | Email | Phone | Handle |
|--------|------|-------|-------|--------|
| Outlook | From header / signature | From/To/CC | — | — |
| Slack | Display name | Profile email | — | @handle |
| WhatsApp | Contact name | — | Phone number | — |
| Signal | Contact name | — | Phone number | — |
| Granola | Participant name | — | — | — |
| Manual | User-provided | User-provided | User-provided | User-provided |

## Merge Rules

Contacts are merged when:
1. Same name + same company (case-insensitive)
2. Same phone number (normalized: strip +, -, spaces)
3. Manual merge via `/vft-fund-tools:add-contact --merge`
