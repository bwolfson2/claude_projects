---
description: Onboard a new company into the deal pipeline with workspace, CRM entry, and initial research
argument-hint: "<company name>"
---

# /new-deal

> Add a new company to the fund's deal flow pipeline.

Onboard this company: $ARGUMENTS

## Execution

1. **Create CRM entry** — Add the deal to `fund/crm/deals.json`:
   ```bash
   python skills/fund-dealflow-orchestrator/scripts/upsert_deal.py \
     --company "$ARGUMENTS" --stage sourced --status active
   ```

2. **Create company workspace** — Set up the per-company folder structure:
   ```bash
   python skills/fund-dealflow-orchestrator/scripts/init_company_workspace.py \
     --company "$ARGUMENTS"
   ```

3. **Initial research** — Use the web-researcher skill to gather basic company info:
   - What the company does
   - Founding team
   - Funding history
   - Key metrics if public

4. **Update dashboard** — Re-render the deal flow view:
   ```bash
   python skills/fund-dealflow-orchestrator/scripts/render_dealflow_dashboard.py
   ```

5. Present the new company record and suggest next actions (intro call, dataroom request, etc.)

## Related Skills

- **fund-dealflow-orchestrator** — Manages the full deal lifecycle
- **web-researcher** — Gathers company intel
- **project-init** — Creates project workspaces for non-DD projects
