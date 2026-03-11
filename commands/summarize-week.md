---
description: Weekly digest across all workstreams — new messages, deal movement, project updates, and action items due
---

# /summarize-week

> What happened this week across the entire fund?

Generate a weekly digest. $ARGUMENTS

## Execution

### Step 1: Message Activity (last 7 days)

```bash
python -c "
import sqlite3
from pathlib import Path
db = Path('fund/metadata/db/ingestion.db')
conn = sqlite3.connect(str(db))
# Messages by source
rows = conn.execute('''
    SELECT source, COUNT(*) as cnt
    FROM messages
    WHERE timestamp >= datetime('now', '-7 days')
    GROUP BY source ORDER BY cnt DESC
''').fetchall()
print('=== New Messages by Channel ===')
total = 0
for source, cnt in rows:
    print(f'  {source}: {cnt}')
    total += cnt
print(f'  TOTAL: {total}')

# Classification stats
rows2 = conn.execute('''
    SELECT cl.match_type, COUNT(*) as cnt
    FROM classification_log cl
    JOIN messages m ON cl.source_id = m.source_id
    WHERE m.timestamp >= datetime('now', '-7 days')
    GROUP BY cl.match_type
''').fetchall()
print()
print('=== Classification Results ===')
for mtype, cnt in rows2:
    print(f'  {mtype}: {cnt}')
conn.close()
"
```

### Step 2: Deal Movement

```bash
python -c "
import json
from datetime import datetime, timedelta
cutoff = (datetime.now() - timedelta(days=7)).isoformat()
with open('fund/crm/deals.json') as f:
    deals = json.load(f)
active = [d for d in deals if d.get('status') == 'active']
recent = [d for d in active if d.get('last_touch', '') >= cutoff[:10]]
stale = [d for d in active if d.get('last_touch', '') < cutoff[:10]]
print(f'=== Deals: {len(active)} active, {len(recent)} touched this week, {len(stale)} stale ===')
for d in recent:
    print(f'  ✅ {d[\"company\"]} — {d.get(\"stage\",\"?\")} (touched {d.get(\"last_touch\",\"?\")})')
for d in stale[:5]:
    print(f'  ⚠️  {d[\"company\"]} — {d.get(\"stage\",\"?\")} (last touch {d.get(\"last_touch\",\"?\")})')
"
```

### Step 3: Project Updates

```bash
python -c "
import json
from datetime import datetime, timedelta
cutoff = (datetime.now() - timedelta(days=7)).isoformat()
with open('projects/projects.json') as f:
    projects = json.load(f)
active = [p for p in projects if p.get('status') == 'active']
recent = [p for p in active if p.get('last_activity', '') >= cutoff[:10]]
print(f'=== Projects: {len(active)} active, {len(recent)} updated this week ===')
for p in recent:
    print(f'  📋 {p[\"name\"]} [{p.get(\"category\",\"?\")}] — {p.get(\"status\",\"?\")}')
"
```

### Step 4: Synthesize Weekly Digest

```markdown
# Weekly Digest — [Date Range]

## Communication Activity
| Channel | Messages | Classified | New Items |
|---------|----------|------------|-----------|
| [source] | [count] | [count] | [count] |

## Deal Pipeline Movement
### Deals Advanced
- [Company] — moved from [stage] to [stage]

### Deals Needing Attention
- [Company] — stale since [date], next action: [action]

## Project Updates
- [Project] — [status update]

## Key Action Items Due This Week
| Action | Owner | Due | Deal/Project |
|--------|-------|-----|-------------|
| [item] | [who] | [when] | [context] |

## Highlights & Flags
- 🚨 [Urgent items]
- 📥 [New datarooms received]
- 📅 [Upcoming meetings]
```

## Related Skills

- **project-tracker** — Unified dashboard renderer
- **deal-project-classifier** — Classification statistics
- **action-extractor** — Action item tracking
