---
description: Summarize a conversation thread — extract decisions, action items, and open questions
argument-hint: "<paste thread or specify source/channel>"
---

# /summarize-thread

> Distill a conversation thread down to what matters.

Summarize this thread: $ARGUMENTS

## Execution

### If user pasted thread content directly:

Process the pasted text immediately using the thread-summarizer skill approach.

### If user specified a source and identifier:

Query the thread from the ingestion database:

```bash
python -c "
import sqlite3, json
from pathlib import Path
db = Path('fund/metadata/db/ingestion.db')
conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row
# Search by subject, channel, or sender
rows = conn.execute('''
    SELECT source, sender, subject, body, timestamp, channel
    FROM messages
    WHERE subject LIKE ? OR channel LIKE ? OR body LIKE ?
    ORDER BY timestamp ASC LIMIT 50
''', ('%$ARGUMENTS%', '%$ARGUMENTS%', '%$ARGUMENTS%')).fetchall()
for r in rows:
    print(f'[{r[\"timestamp\"]}] {r[\"sender\"]}: {r[\"subject\"] or r[\"channel\"]}')
    print(r['body'][:500] if r['body'] else '(no body)')
    print('---')
conn.close()
"
```

### Output Format

```markdown
# Thread Summary: [Topic]

**Source:** [email/slack/whatsapp/signal]
**Participants:** [names]
**Period:** [first message date] → [last message date]
**Messages:** [count]

## Summary
[2-3 sentence narrative of what was discussed and resolved]

## Decisions Made
1. **[Decision]** — [who decided], [date]
2. **[Decision]** — [who decided], [date]

## Action Items
| Action | Owner | Due | Status |
|--------|-------|-----|--------|
| [task] | [who] | [when] | [open] |

## Open Questions
- [Unresolved question]
- [Unresolved question]

## Key Quotes
- "[Important statement]" — [person], [date]
```

## Related Skills

- **thread-summarizer** — Core summarization logic
- **action-extractor** — Action item extraction
