---
name: fund-dealflow-orchestrator
description: Manage a fund-level CRM and diligence workflow across sourced companies, intro calls, dataroom requests, deep diligence, IC prep, term sheets, and portfolio tracking. Use when Codex needs to maintain where the fund is with each company, update next actions and owners, create per-company workspaces, sync diligence outputs into a shared registry, and render a current dashboard from repo-local records.
---

# Fund Dealflow Orchestrator

Operate the repo as a fund operating system, not just a diligence archive. Keep company status, diligence state, next actions, and decision posture in one shared registry.

## Core Workflow

1. Read `references/workflow.md` for the operating sequence.
2. Read `references/stages.md` before changing a company's stage.
3. Read `references/data-model.md` before editing `fund/crm/deals.json`.
4. For a new company, run `scripts/init_company_workspace.py`.
5. After each meeting, memo, or diligence update, update the company record in `fund/crm/deals.json`.
6. Rebuild `fund/crm/dashboard.md` with `scripts/render_dealflow_dashboard.py`.
7. When deep diligence is needed, route the work to `$startup-diligence-orchestrator` and sync the resulting artifacts back into the deal record.

## Working Rules

- Keep exactly one company record per slug in `fund/crm/deals.json`.
- Separate `facts`, `assumptions`, and `next actions`.
- Do not move a company to a later stage without satisfying the exit criteria in `references/stages.md`.
- Always record:
  - current `stage`
  - `decision_posture`
  - `last_touch`
  - `next_action`
  - `next_action_owner`
  - `next_action_due`
- Link the main artifacts: dataroom, diligence memo, short memo, IC note, and meeting notes when they exist.
- If a judgment depends on assumptions, state that in the deal record instead of hiding it in prose.

## Scripts

- `scripts/init_company_workspace.py`
  - Creates `fund/companies/<slug>/...`
  - Seeds a company record in `fund/crm/deals.json`
- `scripts/upsert_deal.py`
  - Updates top-level or nested fields in `fund/crm/deals.json`
- `scripts/render_dealflow_dashboard.py`
  - Renders `fund/crm/dashboard.md` from the registry

## Output Standard

Aim to leave the repo with:

- an up-to-date `fund/crm/deals.json`
- a fresh `fund/crm/dashboard.md`
- a per-company workspace under `fund/companies/<slug>/`
- explicit next actions and owners for every active company

Use the templates in `assets/` when creating or refreshing company workspaces.
