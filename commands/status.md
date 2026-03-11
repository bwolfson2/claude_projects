---
description: Render unified dashboard across all workstreams — DD deals, hiring, research, operations, and communications
---

# /status

> Show the current state of everything the fund is tracking.

Render a unified dashboard showing all active workstreams. $ARGUMENTS

## Execution

1. Run the unified dashboard renderer:
   ```bash
   python skills/project-tracker/scripts/render_unified_dashboard.py
   ```

2. If the user specified a specific area (e.g. "deals", "hiring", "comms"), focus on that section.

3. Present the dashboard output formatted as a clean markdown table.

4. Highlight items that need attention: overdue actions, stale deals, unclassified messages.

## Related Skills

- **project-tracker** — The underlying skill that generates the dashboard data
- **fund-dealflow-orchestrator** — For deal-specific deep dives
- **project-management** — For non-DD project details
