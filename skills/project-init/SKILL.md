---
name: project-init
description: Create a new project workspace from type-specific templates. Handles DD deals, hiring, research, conversations, and operations projects. Use when starting a new due diligence, opening a hiring role, creating a research project, tracking a conversation thread, or spinning up any operational project.
---

# Project Init

Spin up a typed project workspace instantly. Determine the project type from context, scaffold the correct folder structure, seed the registry, and register for classification.

## Trigger Phrases

- "Start a new DD on CompanyX"
- "Open a hiring project for Senior Engineer"
- "Create a research project on AI infrastructure"
- "Track my conversations with John Smith"
- "New project for office move"

## Core Workflow

1. Determine project type from context (dd, hiring, research, conversations, operations).
2. Generate slug from name (kebab-case, max 60 chars).
3. Run `scripts/init_project_workspace.py` with type and name.
4. Verify folder structure created from type template.
5. Verify registry entry added (deals.json for DD, projects.json for all others).
6. Run `fund/metadata/rebuild_index.py` to register in classification index.
7. Render updated dashboard.

## Project Types

### 1. Due Diligence (`dd`)
- Path: `fund/companies/{slug}/`
- Registry: `fund/crm/deals.json`
- Template: `assets/templates/dd/`
- Lifecycle: sourced → screening → first_meeting → dataroom → deep_diligence → ic_prep → decision

### 2. Hiring (`hiring`)
- Path: `projects/hiring/{slug}/`
- Registry: `projects/projects.json`
- Template: `assets/templates/hiring/`
- Lifecycle: open → sourcing → screening → interviewing → offer → closed_hired | closed_unfilled

### 3. Research (`research`)
- Path: `projects/research/{slug}/`
- Registry: `projects/projects.json`
- Template: `assets/templates/research/`
- Lifecycle: scoping → active → synthesis → published | archived

### 4. Conversations (`conversations`)
- Path: `projects/conversations/{slug}/`
- Registry: `projects/projects.json`
- Template: `assets/templates/conversations/`
- Lifecycle: active → dormant → archived

### 5. Operations (`operations`)
- Path: `projects/operations/{slug}/`
- Registry: `projects/projects.json`
- Template: `assets/templates/operations/`
- Lifecycle: active → blocked → completed | archived

## Scripts

- `scripts/init_project_workspace.py`
  - `--type dd|hiring|research|conversations|operations`
  - `--name "Project Name"`
  - `--slug optional-custom-slug`
  - `--owner fund`
  - `--priority medium`
  - `--force` — Overwrite existing files

## Working Rules

- Never create a duplicate slug in the same registry.
- Always populate template files (never leave them empty).
- For DD type, delegate to the existing `fund-dealflow-orchestrator` init when possible.
- Register keywords in the project record for classifier matching.
- After scaffolding, always rebuild the classification index.
