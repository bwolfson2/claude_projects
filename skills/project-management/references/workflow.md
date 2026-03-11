# Project Workflow

## Lifecycle Stages

Projects move through the following stages:

### Planned
- Project is defined and scheduled to start.
- Scope, timeline, owner, and success criteria are documented.
- No work has begun yet.
- Next action: Kickoff and team alignment.

### In Progress
- Active work is underway.
- Team is assigned and engaged.
- Regular updates are being tracked.
- Next action is clear and assigned.
- Exit criteria: Clear completion of milestones or tasks.

### Blocked
- Work is stopped due to external blockers, decisions, or resource constraints.
- Blocker is documented and tracked.
- An owner is responsible for unblocking.
- Next action: Resolve blocker and resume.

### Done
- Project deliverables are complete.
- Success criteria have been met.
- Handoff or launch has occurred.
- Project moves to archived after post-completion review.

### Archived
- Project is complete and no longer active.
- Used for historical reference.
- Can be reactivated if needed.

## Operating Sequence

1. **Intake**
   - New project is added to `projects/projects.json` with `status: planned`.
   - Category, owner, target date, and success criteria are documented.

2. **Kickoff**
   - Move to `status: in_progress`.
   - Team and resources are aligned.
   - First next action is set.

3. **Execution**
   - Regular updates to project status and next actions.
   - Track blockers and assumptions.
   - Update target dates if scope changes.

4. **Unblocking**
   - If blocked, document the blocker and owner responsible for resolution.
   - Set a date to reassess.

5. **Completion**
   - Move to `status: done` when deliverables are met.
   - Document completion date and final notes.

6. **Archive**
   - After completion review, move to `status: archived`.
   - Keep for historical tracking.

## Required Repo Paths

- Registry: `projects/projects.json`
- Dashboard: `projects/dashboard.md`
- Project workspace: `projects/<slug>/` (optional)

## Minimum Fields For Active Projects

- `slug`
- `project_name`
- `category`
- `status`
- `priority`
- `owner`
- `start_date`
- `target_date`
- `next_action`
- `next_action_owner`
- `next_action_due`
- `description`

## Status Transitions

- `planned` → `in_progress` (when team is ready to start)
- `in_progress` → `blocked` (when external blocker occurs)
- `in_progress` → `done` (when deliverables are complete)
- `blocked` → `in_progress` (when blocker is resolved)
- `done` → `archived` (after post-completion review)
- `archived` → `in_progress` (if project is reactivated)
