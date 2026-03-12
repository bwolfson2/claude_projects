---
name: reactive-router
description: Analyze classified messages and determine what reactive actions to take — dataroom processing, meeting prep, deal creation, urgent flagging, and action item extraction. Uses RLM subcommands driven by Claude's reasoning. Auto-invoked after message classification to close the loop between incoming data and fund workflows.
---

# Reactive Router

The intelligence layer between message classification and fund workflow execution. After messages are classified to deals/projects, Claude reads them and decides what *actions* should be taken — using its own reasoning, not pattern matching.

## When to Use

- After running `/vft-fund-tools:monitor` or `/vft-fund-tools:scan-comms`
- When new messages have been classified but not yet acted upon
- When you need to determine the appropriate workflow response to incoming data

## RLM Workflow

### Step 1: Get Pending Messages

```bash
python skills/reactive-router/scripts/route_messages.py pending
```

Returns classified-but-unrouted messages with their classification context (matched slug, match type, confidence, body preview, attachments).

Use `--project midbound` to filter to a specific deal/project.

### Step 2: Review Available Routes

```bash
python skills/reactive-router/scripts/route_messages.py routes
```

Returns the available route types as reference:

| Route | Priority | When to use |
|-------|----------|-------------|
| `term_sheet` | URGENT | Term sheet, SAFE, convertible note, legal investment document |
| `dataroom` | HIGH | Dataroom shared, diligence materials, document batch |
| `meeting` | MEDIUM | Meeting request, calendar invite, scheduling |
| `intro` | MEDIUM | New introduction to a founder or company |
| `funding` | LOW | Funding announcement, round closure |
| `action_items` | LOW | Action items, commitments, deadlines |
| `follow_up` | LOW | Thread continuation with new information |

### Step 3: Reason About Each Message

Read the subject, body preview, attachments, and classification for each pending message. Decide:
- What action should the fund take?
- Is this a dataroom drop? A term sheet? A meeting request? An intro?
- What priority level? (URGENT items get surfaced to the user immediately)
- If multiple routes could apply, pick the highest priority one

### Step 4: Store Decisions

**For individual routes:**
```bash
python skills/reactive-router/scripts/route_messages.py route \
  --message-id 42 --route dataroom --priority HIGH \
  --actions '["download_attachments", "run_dataroom_intake", "run_document_processor"]' \
  --reasoning "Zip attachment with diligence materials for Midbound"
```

**For batches:**
```bash
python skills/reactive-router/scripts/route_messages.py batch-route --decisions '[
  {"message_id": 42, "route": "dataroom", "priority": "HIGH", "actions": ["download_attachments", "run_dataroom_intake"]},
  {"message_id": 43, "route": "meeting", "priority": "MEDIUM", "actions": ["create_meeting_prep"]}
]'
```

**For messages that need no action:**
```bash
python skills/reactive-router/scripts/route_messages.py mark-routed --message-ids 44,45,46
```

### Step 5: Execute Action Plan

After routing, execute each action. For URGENT/HIGH priority items, confirm with the user before proceeding.

**Dataroom received:**
1. Download attachments to `fund/datarooms/{company}_dataroom/`
2. Run `python skills/dataroom-intake/scripts/build_manifest.py`
3. Run `python skills/document-processor/scripts/extract_text.py`
4. Update deal stage

**Term sheet received:**
1. Flag as URGENT — present to user immediately
2. Save to `fund/companies/{slug}/diligence/`
3. Update deal stage to "term_sheet"
4. Suggest running finance-legal-diligence review

**Meeting request:**
1. Create meeting prep note
2. Update last_touch on the deal

**New introduction:**
1. Create deal entry via `classify_messages.py auto-create`
2. Run web research on the company
3. Create workspace

**Action items detected:**
1. Extract action items using action-extractor
2. Append to relevant `next-actions.md`

## Subcommand Reference

| Subcommand | Purpose |
|------------|---------|
| `pending` | List classified-but-unrouted messages |
| `routes` | Show available route types (reference) |
| `route` | Store one routing decision |
| `batch-route` | Store multiple decisions + output action plan |
| `mark-routed` | Mark messages as needing no action |

## Integration

The reactive router is called by:
- `/vft-fund-tools:monitor` (Phase 2)
- `vft-monitor-sweep` scheduled task (daily 8am)
- Manually via `/vft-fund-tools:scan-comms` when reactive routing is desired
