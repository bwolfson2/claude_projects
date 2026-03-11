# Project Registry Data Model

`projects/projects.json` is the source of truth.

## Top-level keys

- `schema_version`
- `fund_name`
- `last_updated`
- `projects`

## Project record fields

- `slug`
  - Unique identifier for the project (e.g., `ops-accounting-2024`, `fundraising-materials-q1`)
- `project_name`
  - Human-readable project title
- `category`
  - One of: `operations`, `legal_corp`, `product`, `fundraising`, `portfolio`
  - See `references/categories.md` for definitions
- `status`
  - One of: `planned`, `in_progress`, `blocked`, `done`, `archived`
  - See `references/workflow.md` for transitions
- `priority`
  - One of: `critical`, `high`, `medium`, `low`
  - Relative to other active projects
- `owner`
  - Name or identifier of primary project owner
- `start_date`
  - Date project began (ISO format: YYYY-MM-DD)
  - Null if not yet started
- `target_date`
  - Planned completion date (ISO format: YYYY-MM-DD)
  - Used for scheduling and priority management
- `description`
  - Brief description of project scope and objectives
- `success_criteria`
  - List of measurable deliverables or outcomes
- `next_action`
  - The immediate next step in the project
- `next_action_owner`
  - Person responsible for the next action
- `next_action_due`
  - When the next action is due (ISO format: YYYY-MM-DD)
- `completion_date`
  - Date project was marked done or archived
  - Null for active projects
- `docs`
  - List of artifact paths (specs, memos, spreadsheets, contracts, etc.)
- `notes`
  - Array of timestamped notes and updates
  - Include decisions, changes in scope, blockers, assumptions
- `blockers`
  - Array of current blockers (if status is `blocked`)
  - Each blocker should include description and owner
- `assumptions`
  - Array of key assumptions the project depends on
  - Reference these if decision is uncertain
- `team`
  - List of team members involved (optional)

## Notes format

Each note should be an object:
```json
{
  "date": "2025-01-15",
  "author": "person_name",
  "content": "Update or decision note"
}
```

## Blockers format

Each blocker should be an object:
```json
{
  "description": "What is blocking progress",
  "owner": "who_is_responsible_for_unblocking",
  "since_date": "2025-01-10"
}
```

## Artifact paths

Use repo-local absolute or repo-relative paths for:

- `project_workspace`
- `spec_document`
- `requirements_document`
- `status_memo`
- `analysis_spreadsheet`
- `contract_document`
- `presentation_deck`
- `meeting_notes`
- Other project-specific artifacts

## Rule

If a judgment depends on assumptions, put the assumption in the record and reference it in notes. Do not hide critical dependencies in prose.
