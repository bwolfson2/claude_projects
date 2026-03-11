---
name: project-management
description: Manage non-DD projects for a VC fund (operations, legal/corp, product, fundraising, portfolio management). Use when Codex needs to track project status, manage timelines, assign owners, create project records, update next actions, and render a current dashboard from repo-local records.
---

# Project Management

Operate the project registry as the fund's operational hub for non-diligence work. Keep project status, timelines, owners, next actions, and priorities in one shared registry.

## Core Workflow

1. Read `references/workflow.md` for the operating sequence.
2. Read `references/categories.md` before assigning a project category.
3. Read `references/data-model.md` before editing `projects/projects.json`.
4. For a new project, create a project record in `projects/projects.json` with a unique slug.
5. After each update, sync the project status in `projects/projects.json`.
6. Rebuild `projects/dashboard.md` with `scripts/render_project_dashboard.py`.
7. Link all relevant artifacts (docs, memos, spreadsheets) in the project record.

## Working Rules

- Keep exactly one project record per slug in `projects/projects.json`.
- Separate `facts`, `assumptions`, and `next actions`.
- Do not change project status without a documented reason.
- Always record:
  - current `status`
  - `category`
  - `priority`
  - `owner`
  - `next_action`
  - `next_action_owner`
  - `next_action_due`
- Link all main artifacts: specs, memos, analyses, contracts, spreadsheets when they exist.
- If a judgment depends on assumptions, state that in the project record instead of hiding it in prose.
- Use explicit target dates for all active projects.

## Scripts

- `scripts/upsert_project.py`
  - Updates top-level or nested fields in `projects/projects.json`
- `scripts/render_project_dashboard.py`
  - Renders `projects/dashboard.md` from the registry

## Output Standard

Aim to leave the repo with:

- an up-to-date `projects/projects.json`
- a fresh `projects/dashboard.md`
- per-project documentation under `projects/<slug>/` (optional but recommended)
- explicit next actions and owners for every active project
- clear target dates and priorities

Use the templates in `assets/` when creating or refreshing project records.
