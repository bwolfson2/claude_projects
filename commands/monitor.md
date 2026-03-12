---
description: Run a full monitoring sweep — scan all channels, classify, and reactively dispatch workflows based on what came in
---

# /monitor

> Scan everything, classify it, and act on what matters.

Run a full monitoring sweep. $ARGUMENTS

## Execution

### Phase 1: Scan All Channels

Run the comms-hub pipeline to pull new messages from all connected channels:

```bash
python skills/comms-hub/scripts/run_pipeline.py
```

This dispatches: Outlook → Slack → WhatsApp → Signal → Granola transcripts, then classifies and applies updates.

### Phase 2: Classify & Route (RLM)

After scanning, classify and route messages using conversational reasoning via RLM subcommands:

**Classify unprocessed messages:**
1. Load context: `python skills/deal-project-classifier/scripts/classify_messages.py context`
2. Get pending: `python skills/deal-project-classifier/scripts/classify_messages.py pending`
3. For each message, reason about which deal/project it belongs to (consider sender domain, known contacts, subject, attachments, recent activity). Batch obvious matches together.
4. Store decisions: `python skills/deal-project-classifier/scripts/classify_messages.py batch-classify --decisions '[...]'`
5. Create new deals/projects for unmatched items: `python skills/deal-project-classifier/scripts/classify_messages.py auto-create --type deal --name "X"`
6. Apply updates: `python skills/deal-project-classifier/scripts/apply_updates.py`

**Route classified messages:**
1. Get pending: `python skills/reactive-router/scripts/route_messages.py pending`
2. Review routes: `python skills/reactive-router/scripts/route_messages.py routes`
3. For each message, decide what action the fund should take (dataroom processing, meeting prep, term sheet flag, intro handling, etc.)
4. Store decisions: `python skills/reactive-router/scripts/route_messages.py batch-route --decisions '[...]'`
5. Mark no-action messages: `python skills/reactive-router/scripts/route_messages.py mark-routed --message-ids ...`

### Phase 3: Execute Reactive Actions

For each routed message, take the appropriate action:

#### 🗂️ Dataroom Received
**Detection:** Attachment with zip/pdf/xlsx + keywords ("dataroom", "data room", "documents", "diligence materials")
**Action:**
1. Download attachments to `fund/datarooms/{company}_dataroom/`
2. Run dataroom-intake: `python skills/dataroom-intake/scripts/build_manifest.py`
3. Run text extraction: `python skills/document-processor/scripts/extract_text.py`
4. Update deal stage to "dataroom_received" if currently earlier

#### 📅 Meeting Request
**Detection:** Keywords ("schedule", "meeting", "call", "catch up", "sync", "coffee chat") or .ics attachment
**Action:**
1. Create meeting prep note in `fund/companies/{slug}/meetings/`
2. If deal exists, update last_touch
3. If new contact, consider creating deal entry
4. Suggest running call-prep before the meeting

#### 📄 Term Sheet / Legal Document
**Detection:** Keywords ("term sheet", "SAFE", "side letter", "convertible note", "subscription agreement")
**Action:**
1. Flag as **URGENT** — notify user immediately
2. Update deal stage to "term_sheet" or "negotiation"
3. Save document to `fund/companies/{slug}/diligence/`
4. Suggest running finance-legal-diligence review

#### 🤝 New Introduction
**Detection:** Keywords ("intro", "introducing", "meet", "connect you with") + unrecognized sender domain
**Action:**
1. Auto-create deal entry via `python skills/fund-dealflow-orchestrator/scripts/upsert_deal.py`
2. Run initial web research on the company
3. Create company workspace
4. Set stage to "sourced"

#### 💰 Funding Announcement
**Detection:** Keywords ("raised", "funding", "round", "series", "seed", "pre-seed") in body
**Action:**
1. Update deal record with funding details
2. If we're tracking this company, flag for follow-up

#### ✅ Action Items Detected
**Detection:** Commitments, deadlines, or task language in message body
**Action:**
1. Extract action items using action-extractor patterns
2. Append to relevant `next-actions.md` file
3. Include in summary output

### Phase 4: Summary Report

Present what was found and what was done:

```markdown
# Monitor Report — [timestamp]

## Scan Results
| Channel | New Messages | Classified | Unmatched |
|---------|-------------|------------|-----------|
| Outlook | [n] | [n] | [n] |
| Slack | [n] | [n] | [n] |
| ... | ... | ... | ... |

## Reactive Actions Taken
### 🚨 Urgent
- [action taken — e.g., "Term sheet received from Acme Corp, flagged for review"]

### 📥 New Items
- [action taken — e.g., "New intro from Jane Smith → created deal for WidgetCo"]

### 📋 Updates Applied
- [action taken — e.g., "Meeting request from Acme → prep note created"]

### ✅ Action Items Extracted
- [item] — assigned to [owner], due [date]

## Items Needing Manual Review
- [message with low classification confidence]
- [ambiguous routing decision]
```

## Related Skills

- **comms-hub** — Channel scanning orchestration
- **reactive-router** — Message routing intelligence
- **deal-project-classifier** — Classification engine
- **fund-dealflow-orchestrator** — Deal management
- **action-extractor** — Action item extraction
- **dataroom-intake** — Dataroom processing
