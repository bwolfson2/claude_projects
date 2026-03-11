# Fund Workflow

## Sequence

1. Source
   Add the company to `fund/crm/deals.json` with `stage: sourced`.
2. Screen
   Record the thesis, source, first contact, and whether an intro or dataroom is needed.
3. First meeting
   Log meeting notes, update `last_touch`, and set a concrete next action.
4. Dataroom and diligence
   Move the company into diligence stages, run the existing diligence skills, and attach the outputs to the company record.
5. IC prep
   Summarize valuation, conviction, open risks, assumptions, and recommendation.
6. Term sheet or pass
   Record decision date, rationale, and post-decision follow-up.
7. Portfolio monitoring
   If invested, keep quarterly updates, risks, asks, and owner notes in the same workspace.

## Required Repo Paths

- Registry: `fund/crm/deals.json`
- Dashboard: `fund/crm/dashboard.md`
- Company workspace: `fund/companies/<slug>/`

## Minimum Fields For Active Companies

- `stage`
- `status`
- `decision_posture`
- `last_touch`
- `next_action`
- `next_action_owner`
- `next_action_due`

## Diligence Handoff

When a company enters `dataroom_requested`, `dataroom_received`, or `deep_diligence`:

- create or refresh the company workspace
- run `$startup-diligence-orchestrator`
- store output paths in the company record
- convert diligence findings into concrete next actions
