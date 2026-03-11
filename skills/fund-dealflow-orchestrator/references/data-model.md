# Deal Registry Data Model

`fund/crm/deals.json` is the source of truth.

## Top-level keys

- `schema_version`
- `fund_name`
- `last_updated`
- `companies`

## Company record fields

- `slug`
- `company_name`
- `status`
  - usually `active`, `parked`, `passed`, or `invested`
- `stage`
  - use the stage names in `stages.md`
- `owner`
- `source`
- `sector`
- `round`
- `raise_usd`
- `valuation_cap_usd`
- `decision_posture`
- `priority`
- `last_touch`
- `next_action`
- `next_action_owner`
- `next_action_due`
- `thesis`
- `open_questions`
- `assumptions`
- `artifacts`
- `diligence`

## Artifact keys

Use repo-local absolute or repo-relative paths for:

- `dataroom`
- `company_workspace`
- `full_report`
- `short_memo`
- `ic_note`
- `meeting_notes`

## Diligence state keys

Use simple states such as:

- `not_started`
- `requested`
- `in_progress`
- `complete`
- `blocked`

Recommended keys:

- `commercial`
- `product_technical`
- `finance_legal`
- `memo`

## Rule

If a judgment depends on assumptions, put the assumption in the record and reflect that in `decision_posture`.
