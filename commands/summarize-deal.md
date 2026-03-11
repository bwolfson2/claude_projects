---
description: Produce a current-state summary for a specific deal — stage, findings, risks, messages, and next actions
argument-hint: "<company name>"
---

# /summarize-deal

> Get the full picture on a deal in one shot.

Summarize this deal: $ARGUMENTS

## Execution

### Step 1: Gather Deal Record

```bash
python -c "
import json, sys
with open('fund/crm/deals.json') as f:
    deals = json.load(f)
match = [d for d in deals if '$ARGUMENTS'.lower() in d.get('company','').lower()]
if match:
    print(json.dumps(match[0], indent=2))
else:
    print('No deal found for: $ARGUMENTS')
    sys.exit(1)
"
```

### Step 2: Pull Recent Messages

Query all messages classified to this deal from the last 30 days:

```bash
python -c "
import sqlite3, json
from pathlib import Path
db = Path('fund/metadata/db/ingestion.db')
conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row
rows = conn.execute('''
    SELECT source, sender, subject, body, timestamp, channel
    FROM messages
    WHERE project_tags LIKE ? AND timestamp >= datetime('now', '-30 days')
    ORDER BY timestamp DESC LIMIT 20
''', ('%$ARGUMENTS%',)).fetchall()
for r in rows:
    print(f'[{r[\"timestamp\"]}] {r[\"source\"]}: {r[\"sender\"]} — {r[\"subject\"] or r[\"channel\"]}')
    print(f'  {(r[\"body\"] or \"\")[:200]}')
    print()
conn.close()
"
```

### Step 3: Pull Dataroom Extractions (if any)

```bash
python skills/document-processor/scripts/query_documents.py \
  --dataroom $(echo "$ARGUMENTS" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')_dataroom --stats 2>/dev/null || echo "No dataroom extractions found"
```

### Step 4: Check Company Workspace

Read the company's workspace files if they exist:
- `fund/companies/{slug}/company.md` — Company overview
- `fund/companies/{slug}/next-actions.md` — Open action items
- `fund/companies/{slug}/diligence/ic-snapshot.md` — IC snapshot
- `fund/companies/{slug}/meetings/notes.md` — Meeting notes

### Step 5: Synthesize

Produce a structured summary:

```markdown
# Deal Summary: [Company]

**Stage:** [current stage] | **Status:** [active/paused/closed]
**Last Touch:** [date] | **Owner:** [name]

## Key Findings
- [Most important discovery from diligence/messages]
- [Second finding]
- [Third finding]

## Recent Activity (last 30 days)
- [Date]: [Summary of interaction]
- [Date]: [Summary of interaction]

## Open Risks
- [Risk 1 — source]
- [Risk 2 — source]

## Dataroom Status
[Extracted / Not yet processed / No dataroom received]

## Action Items
| Action | Owner | Due | Status |
|--------|-------|-----|--------|
| [item] | [who] | [when] | [open/done] |

## Recommended Next Steps
1. [Most important next action]
2. [Second priority]
```

## Related Skills

- **fund-dealflow-orchestrator** — Deal record management
- **document-processor** — Dataroom extraction queries
- **thread-summarizer** — Conversation thread summaries
- **action-extractor** — Action item extraction
- **diligence-memo-writer** — For a full IC memo (use `/vft-fund-tools:write-memo` instead)
