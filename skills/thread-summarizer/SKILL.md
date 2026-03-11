---
name: thread-summarizer
description: Summarize conversation threads across any project type, preserving key points and decisions. Use when a conversation thread (email, Slack, WhatsApp) needs a concise summary.
---

# Thread Summarizer

Produce concise summaries of conversation threads. Preserve decisions, commitments, and context that matter for the project while discarding noise.

This skill works across all project types: due diligence, hiring, research, conversations, and operations.

## Workflow

1. Read the tagged messages or conversation thread for the project.
2. Identify the channel type (email, Slack, WhatsApp, meeting chat, etc.).
3. Order messages chronologically if not already ordered.
4. Extract key points, decisions made, questions raised, and action items.
5. Identify participants and their roles or positions in the discussion.
6. Produce a concise summary following the output standard below.

## Working Rules

- Attribute decisions and commitments to the person who made them. Use names, not pronouns.
- Preserve exact figures, dates, and deadlines as stated. Do not paraphrase numbers.
- If a decision was reversed or amended later in the thread, show the final state and note the change.
- Distinguish between firm decisions ("we will do X") and open questions ("should we do X?").
- Omit pleasantries, small talk, and logistical back-and-forth (scheduling, acknowledgments) unless they contain substantive information.
- If the thread references external documents or links, list them in the references section.
- For long threads (20+ messages), group by subtopic rather than summarizing linearly.
- Flag any unresolved disagreements between participants.
- Keep the summary to roughly one-tenth the length of the original thread. Shorter is better if nothing is lost.

## Output Standard

Each thread summary must contain these sections:

- **Thread metadata**: channel, date range, participant list.
- **Summary**: concise narrative of what was discussed and concluded.
- **Decisions**: numbered list of decisions made, each attributed to a person and dated.
- **Action items**: who committed to do what, with deadlines if stated.
- **Open questions**: unresolved issues that still need answers.
- **References**: external documents, links, or artifacts mentioned in the thread.

Adapt the level of detail to the project type. Due diligence threads need precise attribution; casual conversation threads need less formality.
