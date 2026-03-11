---
name: deal-project-classifier
description: Classify ingested emails and transcripts by matching them to existing deals or projects using rule-based scoring. Auto-creates new entries for unrecognized items. Updates deal/project status and triggers tracker sync. Use when new emails or transcripts need classification, or to batch-process unclassified items.
---

# VFT Deal & Project Classifier

Classify emails and transcripts from the ingestion database into existing deals or projects. Uses rule-based confidence scoring with domain matching, keyword matching, participant matching, and recency signals. Unmatched items above a creation threshold auto-create new deal or project entries.

## Prerequisites

- Ingestion database at `fund/metadata/db/ingestion.db` with populated `emails` and/or `transcripts` tables
- `company_index` and `project_index` tables rebuilt (run `fund/metadata/rebuild_index.py` if stale)
- `fund/crm/deals.json` and `projects/projects.json` accessible

## Core Workflow

1. **Query** the ingestion DB for unclassified items (`classified = 0`)
2. **Rebuild indexes** from current deals.json and projects.json (ensures fresh data)
3. **For each unclassified item**, score against all companies and projects:
   - Domain match (40% weight)
   - Keyword match (35% weight)
   - Participant match (20% weight)
   - Recency bonus (5% weight)
4. **Classify** based on highest confidence score:
   - Score ≥ 0.6 → Match to the deal/project with highest score
   - Score 0.3–0.59 → Low confidence match, flag for review
   - Score < 0.3 → No match, auto-create new entry
5. **Apply updates** to matched deals/projects (update last_touch, notes, etc.)
6. **Auto-create** new deal or project entries for truly unmatched items
7. **Log** all classifications in `classification_log` table
8. **Trigger** tracker-sync to update the Excel master tracker

## Classification Algorithm

### Domain Match (weight: 0.40)

```
For emails:
  - Extract sender_domain from email
  - Match against company_index.domains
  - Exact match = 1.0, subdomain match = 0.7

For transcripts:
  - Extract domains from participant emails
  - Match against company_index.domains
  - Any participant domain match = 0.8
```

### Keyword Match (weight: 0.35)

```
For emails:
  - Tokenize subject + body_preview
  - Match against company_index.keywords and project_index.keywords
  - Company name exact match in subject = 1.0
  - Keyword overlap ratio (matched / total keywords) = proportional score

For transcripts:
  - Tokenize title + summary
  - Same matching logic as emails
```

### Participant Match (weight: 0.20)

```
For emails:
  - Match sender + recipients against company_index.contact_emails
  - Exact email match = 1.0

For transcripts:
  - Match participant list against company_index.contact_emails and project_index.contact_emails
  - Any match = 0.8, multiple matches = 1.0
```

### Recency Bonus (weight: 0.05)

```
  - Company/project last_touch within 7 days = 1.0
  - Within 30 days = 0.5
  - Older = 0.0
```

### Final Score

```
final = (domain_score * 0.40) + (keyword_score * 0.35) + (participant_score * 0.20) + (recency_score * 0.05)
```

## Auto-Create Logic

When an item scores < 0.3 against all known entities:

### New Deal Detection
Signals that suggest a deal (vs. project):
- Sender domain is a startup (not a known vendor/service/internal)
- Subject contains: "intro", "pitch", "fundraise", "round", "investment", "deck", "SAFE", "term sheet"
- Participants include a founder title keyword

If deal-like → call `upsert_deal.py` with:
- `company_name`: Inferred from sender domain or subject
- `slug`: Generated from company name
- `stage`: `sourced` (initial stage)
- `source`: `email_scanner` or `transcript_ingestion`
- `status`: `active`

### New Project Detection
Everything else → call `upsert_project.py` with:
- `project_name`: Inferred from subject/title
- `slug`: Generated from name
- `category`: `uncategorized` (user refines later)
- `status`: `active`

## Scripts

### `scripts/classify_batch.py` (v1 — legacy emails/transcripts tables)
Original classification engine for separate email and transcript tables.
- `--dry-run` — Score and log without applying updates
- `--threshold FLOAT` — Override confidence threshold (default: 0.6)
- `--source-type email|transcript|all` — Process only one type (default: all)
- `--rebuild-index` — Force index rebuild before classifying (default: true)

### `scripts/classify_messages.py` (v2 — unified messages table)
Enhanced classifier for the unified messages table. Uses the same scoring algorithm but works with all source types (Outlook, Slack, WhatsApp, Signal, Granola, web scrapes).
- `--dry-run` — Score and log without applying updates
- `--threshold FLOAT` — Override confidence threshold (default: 0.6)
- `--source outlook|slack|whatsapp|signal|granola|web|all` — Filter by source
- `--rebuild-index` — Force index rebuild before classifying (default: true)
- `--llm-fallback` — Enable LLM-based classification for ambiguous items (score 0.30-0.59)

**Prefer classify_messages.py for all new work.** classify_batch.py is kept for backward compatibility.

### `scripts/apply_updates.py`
Takes classification results and updates the pipeline.
- Updates `last_touch` on matched deals/projects
- Creates notes entries for matched items
- Auto-creates new deals/projects for unmatched items
- Runs tracker-sync at the end
- `--dry-run` — Preview changes without writing

### `scripts/rebuild_index.py`
Symlink or direct call to `fund/metadata/rebuild_index.py`.
Rebuilds company_index and project_index from current JSON files.

## Manual Override

### Reclassify an Item
To override an automatic classification:
1. Find the classification in `classification_log` (query by source_type + source_id)
2. Update `matched_slug` and `match_type` to the correct values
3. Set `reviewed = 1` to mark as human-confirmed
4. Re-run `apply_updates.py` to apply the corrected classification

### Prevent Auto-Create
Set environment variable `VFT_NO_AUTO_CREATE=1` to disable auto-creation of new entries.
Items scoring < 0.3 will be logged as `unclassified` instead.

## Classification Log Schema

Each classification produces a log entry with:
- `source_type`: 'email' or 'transcript'
- `source_id`: ID from the emails/transcripts table
- `matched_slug`: The deal/project slug it matched to (NULL if new)
- `match_type`: 'deal', 'project', 'new_deal', 'new_project', 'unclassified'
- `confidence`: Final composite score (0.0–1.0)
- `rule_hits`: JSON object detailing which rules fired and their individual scores

Example `rule_hits`:
```json
{
  "domain": {"score": 0.85, "match": "midbound.com", "source": "sender_domain"},
  "keyword": {"score": 0.6, "matches": ["midbound", "saas"], "total_keywords": 6},
  "participant": {"score": 0.0, "note": "no contact email matches"},
  "recency": {"score": 1.0, "last_touch_days": 5}
}
```

## Cron Integration

This skill is called by the `classify-batch-2h` cron every 2 hours Mon–Fri.
The cron runs: `classify_batch.py --rebuild-index` → `apply_updates.py`

## Working Rules

- Never overwrite a human-reviewed classification (`reviewed = 1`)
- Always rebuild indexes before classification to catch recent deal/project changes
- Log every classification, even low-confidence ones — the log is the audit trail
- When auto-creating, set `source` field to `email_scanner` or `transcript_ingestion` so the origin is traceable
- After all updates, run tracker-sync to keep the Excel master tracker current
