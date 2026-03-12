# VFT Classification — Reasoning Guidance

This is reference material for Claude when classifying messages. These are signals to consider, not a formula — use your judgment.

## Strong Signals (high confidence)

| Signal | What to look for |
|--------|-----------------|
| **Domain match** | Sender email domain matches a known company's domain (e.g., `ceo@midbound.com` → Midbound deal) |
| **Known contact** | Sender or recipient is a known contact email in a deal/project's contact list |
| **Company name in subject** | Subject line explicitly mentions a company name we're tracking |
| **Same thread** | Reply or forward in an ongoing thread already classified to a deal/project |

## Moderate Signals (use in combination)

| Signal | What to look for |
|--------|-----------------|
| **Keyword relevance** | Subject/body mentions topics closely related to a deal (product name, sector terms, deal-specific jargon) |
| **Recent activity** | There's been recent communication with this entity (within last 1-2 weeks) |
| **Attachment type** | Deck, financial model, legal doc → likely deal-related |
| **Multiple signal overlap** | Domain + keyword + recent activity together = high confidence even if each alone is moderate |

## Weak Signals (consider but don't rely on alone)

| Signal | What to look for |
|--------|-----------------|
| **Generic keywords** | Common terms like "meeting", "update", "follow up" — could apply to any entity |
| **Subdomain match** | Sender on a subdomain of a known company (e.g., `info.company.com`) |
| **Forwarded content** | Third-party forwards may not be about the forwarder's company |

## New Entity Detection

When a message doesn't match any existing deal or project, decide whether to create:

### Create as **new deal** when:
- Sender is from an unknown startup domain
- Content involves investment language (fundraise, pitch, round, SAFE, valuation)
- It's an introduction to a founder or company
- A pitch deck or term sheet is attached

### Create as **new project** when:
- Content is operational (legal, admin, fund management, research)
- Sender is internal or a known service provider
- Topic doesn't involve a specific company investment

### New deal defaults
- Stage: `sourced`, Status: `active`, Source: `auto_classifier`

### New project defaults
- Category: `uncategorized`, Status: `active`

## Manual Override

To override a classification:
1. Query: `SELECT * FROM classification_log WHERE source_type='message' AND source_id=N`
2. Update: `UPDATE classification_log SET matched_slug='correct-slug', match_type='deal', reviewed=1 WHERE id=M`
3. Re-run: `python apply_updates.py`

Setting `reviewed = 1` prevents future automatic overwrite.

## Environment Variables

| Variable | Effect |
|----------|--------|
| `VFT_NO_AUTO_CREATE=1` | Disable auto-creation of new deals/projects |
