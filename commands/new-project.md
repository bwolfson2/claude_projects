---
description: Create a new project workspace from templates — supports DD, hiring, research, conversations, and operations
argument-hint: "<project type> <project name>"
---

# /new-project

> Spin up a new project with the right templates for its type.

Create this project: $ARGUMENTS

## Supported Project Types

| Type | Example | Templates |
|------|---------|-----------|
| `dd` | Due diligence on a startup | company.md, next-actions.md |
| `hiring` | Open role to fill | role.md, pipeline.md, interview-scorecard.md |
| `research` | Market or competitor research | brief.md, findings.md |
| `conversations` | Track a thread across channels | context.md, thread.md, action-items.md |
| `operations` | Internal fund ops project | project.md, next-actions.md |

## Execution

1. **Parse arguments** — Extract project type and name from `$ARGUMENTS`.

2. **Initialize workspace:**
   ```bash
   python skills/project-init/scripts/init_project_workspace.py \
     --type <type> --name "<project name>"
   ```

3. **Register in project tracker:**
   ```bash
   python skills/project-management/scripts/upsert_project.py \
     --name "<project name>" --category <type> --status active
   ```

4. Present the created workspace structure and suggest first actions.

## Related Skills

- **project-init** — Template-based workspace creation
- **project-management** — Project lifecycle management
- **fund-dealflow-orchestrator** — For DD-specific deal tracking
