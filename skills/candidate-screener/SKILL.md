---
name: candidate-screener
description: Evaluate resumes and candidate profiles against a job description, producing a structured scorecard with fit assessment. Use when screening candidates for hiring projects.
---

# Candidate Screener

Score candidates against the role requirements defined in the hiring project. Produce a structured scorecard that captures fit, strengths, concerns, and a clear hire/pass recommendation so the hiring lead can triage quickly.

## Trigger Phrases

- "Screen this candidate for the role"
- "Evaluate this resume against the job description"
- "Score candidate for {role}"
- "Review this profile for the hiring project"
- "Rate this applicant"

## Prerequisites

- A hiring project must exist at `projects/hiring/{slug}/` (use `project-init` skill if needed).
- The project must contain a `role.md` with title, level, requirements, and nice-to-haves.
- The candidate profile or resume must be available as a file, pasted text, or URL.

## Core Workflow

1. **Load role requirements**
   - Read `projects/hiring/{slug}/role.md` for the role definition.
   - Extract must-have requirements, nice-to-haves, level expectations, and team context.
   - If role.md is missing or incomplete, stop and ask the user to fill it in first.

2. **Ingest candidate material**
   - Read the candidate resume, LinkedIn profile, portfolio, or any supplied documents.
   - If the source is a URL, use the `web-researcher` skill to extract profile data.
   - Normalize the candidate data into: experience, education, skills, projects, signals.

3. **Score against requirements**
   - For each must-have requirement, assign a rating: strong | adequate | weak | missing.
   - For each nice-to-have, assign: present | absent.
   - Assess level fit: under-leveled | on-target | over-leveled.
   - Evaluate culture and team signals where evidence exists.

4. **Produce scorecard**
   - Generate a structured scorecard using the format below.
   - Tie every rating to specific evidence from the candidate material.
   - Flag gaps where the resume is silent on a key requirement.
   - State an overall recommendation: advance | hold | pass.

5. **Save and index**
   - Generate a candidate slug from the candidate name (kebab-case).
   - Save the scorecard to `projects/hiring/{slug}/candidates/{candidate-slug}.md`.
   - If the candidates/ folder does not exist, create it.

## Output Standard

### Scorecard Format

```markdown
# {Candidate Name} -- {Role Title} Scorecard

**Screened:** {YYYY-MM-DD}
**Source:** {resume | linkedin | referral | inbound}
**Recommendation:** advance | hold | pass

---

## Fit Summary

{2-3 sentence overall assessment}

## Must-Have Requirements

| Requirement | Rating | Evidence |
|---|---|---|
| {req} | strong/adequate/weak/missing | {specific evidence} |

## Nice-to-Haves

| Nice-to-Have | Present? | Notes |
|---|---|---|
| {item} | yes/no | {notes} |

## Level Assessment

{On-target / under-leveled / over-leveled with reasoning}

## Strengths

- {strength with evidence}

## Concerns

- {concern with evidence or gap noted}

## Open Questions

- {questions to explore in interview if advanced}
```

## Working Rules

- Never fabricate evidence; if the resume is silent on a requirement, rate it "missing" and note the gap.
- Prefer concrete signals (years of experience, named technologies, shipped projects) over vague claims.
- If a candidate is borderline, recommend "hold" and list the specific questions that would resolve the decision.
- Do not penalize candidates for formatting or resume style; focus on substance.
- Treat all candidate data as confidential; do not share across projects.
