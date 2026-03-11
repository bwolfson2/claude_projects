---
name: interview-coordinator
description: Draft interview plans, create scorecards, and suggest scheduling for hiring projects. Use when planning interviews for a role.
---

# Interview Coordinator

Design a structured interview process for a hiring project. Generate an interview plan with stages, questions calibrated to the role, scorecard templates for each interviewer, and scheduling guidance. Save all artifacts to the project workspace so the hiring team can execute consistently.

## Trigger Phrases

- "Plan the interview process for this role"
- "Create interview questions for {role}"
- "Build a scorecard for the interviews"
- "Set up the interview loop for {slug}"
- "Draft an interview plan"

## Prerequisites

- A hiring project must exist at `projects/hiring/{slug}/` (use `project-init` skill if needed).
- The project must contain a `role.md` with title, level, requirements, and team context.
- Candidate scorecards in `candidates/` are helpful but not required.

## Core Workflow

1. **Load role context**
   - Read `projects/hiring/{slug}/role.md` for role definition, requirements, and level.
   - Read any existing candidate scorecards in `candidates/` to understand the pipeline stage.
   - Identify the key competencies to assess: technical skills, domain knowledge, collaboration, leadership.

2. **Design interview stages**
   - Define 3-5 interview stages appropriate to the role level and type.
   - For each stage, specify: purpose, format (phone/video/onsite/take-home), duration, interviewer profile.
   - Common stages: recruiter screen, hiring manager screen, technical assessment, team fit, executive/values.
   - Adjust depth for seniority: junior roles need fewer stages; senior/exec roles need more.

3. **Generate questions per stage**
   - Write 5-8 questions per stage, mapped to specific requirements from role.md.
   - Include a mix of behavioral, situational, and technical questions.
   - For technical stages, include practical exercises or take-home prompts where appropriate.
   - Add follow-up probes for each question to help interviewers dig deeper.
   - Flag which questions are must-ask versus optional.

4. **Create scorecard templates**
   - For each stage, generate a scorecard template the interviewer fills out post-interview.
   - Include the competencies being assessed, a rating scale, and space for evidence notes.
   - Add a section for overall recommendation per stage: strong advance | advance | hold | pass.

5. **Draft scheduling guidance**
   - Suggest interview cadence (e.g., complete loop within 5 business days of screen).
   - Note dependencies between stages (e.g., technical must pass before onsite).
   - Recommend debrief timing and format.

6. **Save artifacts**
   - Save the interview plan to `projects/hiring/{slug}/interview-plan.md`.
   - Save individual scorecard templates to `projects/hiring/{slug}/scorecards/{stage-slug}-scorecard.md`.
   - Create the scorecards/ folder if it does not exist.

## Output Standard

### Interview Plan Format

```markdown
# Interview Plan -- {Role Title}

**Created:** {YYYY-MM-DD}
**Stages:** {count}
**Target loop duration:** {X business days}

---

## Stage 1: {Stage Name}

**Purpose:** {what this stage assesses}
**Format:** {phone | video | onsite | take-home}
**Duration:** {minutes}
**Interviewer profile:** {who should conduct this}

### Questions

1. {Question} *(maps to: {requirement})*
   - Follow-up: {probe}
2. ...

### Must-Ask

- {critical question that must not be skipped}

---

## Debrief Process

{How and when the team should debrief}
```

### Scorecard Template Format

```markdown
# {Stage Name} Scorecard -- {Role Title}

**Candidate:** _______________
**Interviewer:** _______________
**Date:** _______________

| Competency | Rating (1-4) | Evidence |
|---|---|---|
| {competency} | | |

**Overall:** strong advance | advance | hold | pass

**Notes:**

```

## Working Rules

- Tailor questions to the specific role; never use generic question banks without adaptation.
- Ensure every must-have requirement from role.md is assessed in at least one stage.
- Avoid illegal or inappropriate questions (protected characteristics, personal life).
- Keep take-home exercises under 3 hours of estimated effort; respect candidate time.
- Include at least one question per stage that tests for the role's biggest risk factor.
- If the role is cross-functional, include a stage with a stakeholder from the partner team.
