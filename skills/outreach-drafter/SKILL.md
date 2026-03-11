---
name: outreach-drafter
description: Write personalized outreach messages for candidate sourcing. Use when reaching out to potential candidates for a hiring project.
---

# Outreach Drafter

Craft personalized outreach messages that connect the candidate's background to the role's opportunity. Produce messages that are concise, genuine, and specific enough to earn a reply from passive candidates.

## Trigger Phrases

- "Draft an outreach message for this candidate"
- "Write a sourcing email for {candidate}"
- "Reach out to {name} about the {role}"
- "Create a cold message for this profile"
- "Write a follow-up message for {candidate}"

## Prerequisites

- A hiring project must exist at `projects/hiring/{slug}/` with a `role.md`.
- A candidate profile must be available: resume, LinkedIn URL, scorecard in `candidates/`, or pasted text.
- If the candidate source is a URL, the `web-researcher` skill must be available.

## Core Workflow

1. **Load role context**
   - Read `projects/hiring/{slug}/role.md` for the role pitch: title, team, mission, what makes the role compelling.
   - Identify the top 2-3 selling points of the role (impact, team, technology, growth, comp).
   - Note the hiring stage: is this cold outreach, warm intro, or follow-up?

2. **Ingest candidate profile**
   - Read the candidate's resume, LinkedIn profile, or scorecard from `candidates/`.
   - If the source is a URL, use the `web-researcher` skill to extract the profile.
   - Extract: current role, notable projects, technologies, career trajectory, public writing or talks.
   - Identify 2-3 specific hooks -- things in the candidate's background that connect to the role.

3. **Craft the message**
   - Open with a specific, personalized hook referencing something the candidate has done.
   - Connect the hook to why this role would be interesting for them specifically.
   - Keep the pitch to 2-3 sentences: what the company does, what the role involves, why it matters.
   - Close with a low-friction ask: 15-minute call, not a full interview commitment.
   - Keep total length under 150 words for initial outreach; under 100 words for follow-ups.

4. **Generate variants if requested**
   - If the user asks, produce 2-3 message variants with different hooks or tones.
   - Variants: professional, casual, technical-peer (adjust based on candidate seniority and culture).

5. **Save draft**
   - Save the outreach message to `projects/hiring/{slug}/templates/outreach-{candidate-slug}.md`.
   - Create the templates/ folder if it does not exist.
   - If multiple variants are generated, save all variants in the same file.

## Output Standard

### Outreach Message Format

```markdown
# Outreach -- {Candidate Name} for {Role Title}

**Drafted:** {YYYY-MM-DD}
**Type:** cold | warm-intro | follow-up
**Channel:** email | linkedin | referral-note

---

## Message

Subject: {subject line}

{message body}

---

## Personalization Notes

- Hook used: {what specific candidate detail was referenced}
- Role selling points: {which aspects of the role were highlighted}
- Connection: {how the hook ties to the role}
```

### Variant Format (when multiple)

```markdown
## Variant A: {tone label}

Subject: {subject line}

{message body}

## Variant B: {tone label}

Subject: {subject line}

{message body}
```

## Working Rules

- Never use generic templates; every message must reference something specific to the candidate.
- Do not exaggerate the role, comp, or company trajectory; credibility earns replies.
- Avoid buzzwords and recruiter cliches ("rockstar", "exciting opportunity", "fast-paced environment").
- Keep the first sentence about the candidate, not the company.
- If the candidate's profile is thin (no public projects, minimal info), note this and ask the user for additional context before drafting.
- For follow-ups, reference the previous message and add a new angle rather than repeating the same pitch.
- Respect candidate preferences: if a profile says "not open to opportunities", flag this to the user before drafting.
- Treat all candidate information as confidential; do not reference private details from internal scorecards in external messages.
