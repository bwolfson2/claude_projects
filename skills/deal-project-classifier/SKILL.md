---
name: deal-project-classifier
description: Classify ingested messages by matching them to existing deals or projects using Claude's conversational reasoning via RLM subcommands. Auto-creates new entries for unrecognized items. Use when new messages need classification, or to batch-process unclassified items.
---

# VFT Deal & Project Classifier

Classify messages from the ingestion database into existing deals or projects. Uses an RLM (Recursive Language Model) pattern where Claude drives the classification conversationally via thin data-access subcommands — no scoring algorithm, no keyword matching.

## Prerequisites

- Ingestion database at `fund/metadata/db/ingestion.db` with populated `messages` table
- `company_index` and `project_index` tables (auto-rebuilt by the `context` subcommand)
- `fund/crm/deals.json` and `projects/projects.json` accessible

## RLM Workflow

### Step 1: Load Context

```bash
python skills/deal-project-classifier/scripts/classify_messages.py context
```

Returns all known deals and projects with their matching signals:
- **Deals:** slug, company name, domains, keywords, contact emails, last touch, stage, status
- **Projects:** slug, name, keywords, contact emails, status, type
- **Recent classifications:** last 20 entries for reference

Use `--active-only` to filter out passed deals and archived projects.

### Step 2: Get Pending Messages

```bash
python skills/deal-project-classifier/scripts/classify_messages.py pending
```

Returns unclassified messages with previews (id, source, sender, sender_domain, subject, body_preview, attachments, timestamp).

Use `--source outlook` to filter by source. Use `--limit 100` for larger batches.

If the 300-character preview is insufficient for a message:
```bash
python skills/deal-project-classifier/scripts/classify_messages.py detail --id 42
```

### Step 3: Classify Messages

For each message (or batch of similar messages), reason about which deal or project it belongs to:

**Signals to consider:**
- Sender email domain — does it match a known company's domain?
- Known contacts — is the sender/recipient a known contact for a deal?
- Subject and body content — does it reference a company name, deal terms, or project topic?
- Attachments — dataroom materials, decks, legal docs suggest deal-related
- Recent activity — was there recent communication with this entity?
- Thread context — is this part of an ongoing conversation?

**For straightforward matches** (clear domain match, known contact), batch them:
```bash
python skills/deal-project-classifier/scripts/classify_messages.py batch-classify --decisions '[
  {"message_id": 42, "slug": "midbound", "match_type": "deal", "confidence": 0.95, "reasoning": {"domain_match": "midbound.com"}},
  {"message_id": 43, "slug": "midbound", "match_type": "deal", "confidence": 0.90, "reasoning": {"same_thread": true}}
]'
```

**For individual classifications:**
```bash
python skills/deal-project-classifier/scripts/classify_messages.py classify \
  --message-id 42 --slug midbound --match-type deal --confidence 0.9 \
  --reasoning '{"domain": "midbound.com", "contact": "ceo@midbound.com"}'
```

### Step 4: Handle Unmatched Messages

When a message doesn't match any existing entity, decide whether it's a new deal or a new project:

- **New deal signals:** Startup domain, investment language, founder introductions, pitch decks
- **New project signals:** Internal operations, legal/admin, research topics

```bash
python skills/deal-project-classifier/scripts/classify_messages.py auto-create \
  --type deal --name "WidgetCo" --message-id 44 \
  --extra '{"sector": "SaaS", "stage": "sourced"}'
```

### Step 5: Apply Updates

After classification, propagate changes to the deal/project JSON files:
```bash
python skills/deal-project-classifier/scripts/apply_updates.py
```

## Subcommand Reference

| Subcommand | Purpose |
|------------|---------|
| `pending` | List unclassified messages with previews |
| `context` | Show all deals/projects with matching signals |
| `detail --id N` | Full message content |
| `classify` | Store one classification decision |
| `batch-classify` | Store multiple decisions at once |
| `auto-create` | Create new deal/project for unmatched items |

## Manual Override

To override an automatic classification:
1. Find the classification in `classification_log` (query by source_type + source_id)
2. Update `matched_slug` and `match_type` to the correct values
3. Set `reviewed = 1` to mark as human-confirmed (prevents future overwrite)
4. Re-run `apply_updates.py`

## Working Rules

- Never overwrite a human-reviewed classification (`reviewed = 1`)
- Always use the `context` subcommand before classifying to ensure fresh indexes
- Log every classification — the classification_log is the audit trail
- When auto-creating, set the source field so the origin is traceable
- After all updates, run tracker-sync to keep the master tracker current
- Batch obvious matches (same domain, same thread) for efficiency
- Only reason message-by-message when context is ambiguous
