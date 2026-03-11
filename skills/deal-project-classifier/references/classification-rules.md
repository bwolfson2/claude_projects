# VFT Classification Rules

## Scoring Weights

| Signal | Weight | Description |
|--------|--------|-------------|
| Domain Match | 40% | Sender/participant email domain matches known company domains |
| Keyword Match | 35% | Subject/body/title contains company name or project keywords |
| Participant Match | 20% | Known contact emails appear in sender/recipients/participants |
| Recency Bonus | 5% | Entity was recently touched (within 7 days = full bonus) |

## Confidence Thresholds

| Score Range | Action |
|-------------|--------|
| ≥ 0.60 | High confidence match → auto-classify and update pipeline |
| 0.30–0.59 | Low confidence match → classify but flag for review |
| < 0.30 | No match → auto-create new deal or project entry |

## Auto-Create Detection

### Deal-Like Signals
Keywords that suggest the item is deal-related:
- intro, pitch, fundraise, round, investment, deck
- SAFE, term sheet, valuation, cap table
- pre-seed, seed, series, venture, startup, founder
- raise, dilution, convertible, equity

If ≥ 1 deal keyword found → create as new deal
If 0 deal keywords → create as new project

### New Deal Defaults
- Stage: `sourced`
- Source: `auto_email_scanner` or `auto_transcript_ingestion`
- Priority: `medium`
- Next action: "Review auto-created deal entry and complete details"

### New Project Defaults
- Category: `uncategorized`
- Status: `active`
- Priority: `medium`

## Manual Override

To override a classification:
1. Query: `SELECT * FROM classification_log WHERE source_type='email' AND source_id=N`
2. Update: `UPDATE classification_log SET matched_slug='correct-slug', match_type='deal', reviewed=1 WHERE id=M`
3. Re-run: `python apply_updates.py`

## Environment Variables

| Variable | Effect |
|----------|--------|
| `VFT_NO_AUTO_CREATE=1` | Disable auto-creation of new deals/projects |
