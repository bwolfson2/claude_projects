---
name: reactive-router
description: Analyze classified messages and determine what reactive actions to take — dataroom processing, meeting prep, deal creation, urgent flagging, and action item extraction. Auto-invoked after message classification to close the loop between incoming data and fund workflows.
---

# Reactive Router

The intelligence layer between message classification and fund workflow execution. After messages are classified to deals/projects, the reactive router determines what *actions* should be taken based on message content, attachments, and context.

## When to Use

- After running `/vft-fund-tools:monitor` or `/vft-fund-tools:scan-comms`
- When new messages have been classified but not yet acted upon
- When you need to determine the appropriate workflow response to incoming data

## How It Works

```
Classified Messages (ingestion.db)
    ↓
route_messages.py (pattern matching on keywords, attachments, metadata)
    ↓
Action Plan (JSON: message_id, route, action, priority)
    ↓
Execute: dataroom-intake / deal creation / meeting prep / urgent flag / action extraction
    ↓
Mark as routed (routed_at timestamp in messages table)
```

## Routing Rules

| Route | Detection Patterns | Priority | Action |
|-------|-------------------|----------|--------|
| `dataroom` | Attachments + "dataroom", "data room", "diligence materials", "documents attached" | HIGH | Run dataroom-intake → document-processor |
| `term_sheet` | "term sheet", "SAFE", "side letter", "convertible note" | URGENT | Flag, update deal stage, save to diligence/ |
| `meeting` | "schedule", "meeting", "call", "sync", "calendar invite", .ics | MEDIUM | Create meeting prep, update last_touch |
| `intro` | "intro", "introducing", "connect you with", "meet" + new domain | MEDIUM | Create deal, web research, workspace |
| `funding` | "raised", "funding", "series", "round", "closed" | LOW | Update deal record |
| `action_items` | Commitment language, deadlines, "will send", "by Friday" | LOW | Extract → append to next-actions.md |
| `follow_up` | Reply to existing classified thread | LOW | Update last_touch, check for new info |

## Running the Router

```bash
# Route all unrouted classified messages
python skills/reactive-router/scripts/route_messages.py

# Dry run — show what would be routed without marking
python skills/reactive-router/scripts/route_messages.py --dry-run

# Route messages for a specific deal/project only
python skills/reactive-router/scripts/route_messages.py --project midbound
```

## Output Format

The router outputs a JSON action plan:

```json
[
  {
    "message_id": 42,
    "source": "outlook",
    "sender": "founder@startup.com",
    "subject": "Dataroom shared",
    "route": "dataroom",
    "priority": "HIGH",
    "matched_project": "midbound",
    "actions": [
      "download_attachments",
      "run_dataroom_intake",
      "run_document_processor",
      "update_deal_stage:dataroom_received"
    ],
    "reason": "Attachment detected + keyword 'dataroom' in subject"
  }
]
```

Claude Code then executes each action in the plan, confirming with the user for HIGH/URGENT items.

## Integration

The reactive router is called automatically by:
- `/vft-fund-tools:monitor` (Phase 2)
- `vft-monitor-sweep` scheduled task (daily 8am)
- Manually via `/vft-fund-tools:scan-comms` when reactive routing is desired
