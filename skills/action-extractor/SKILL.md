---
name: action-extractor
description: Extract action items from messages and meeting transcripts, identifying owners and due dates. Use when processing new messages or transcripts to find commitments and tasks.
---

# Action Extractor

Extract action items, commitments, and deadlines from messages and transcripts. Identify who owns each item and when it is due.

This skill works across all project types: due diligence, hiring, research, conversations, and operations.

## Workflow

1. Read the message or transcript content provided.
2. Identify every statement that constitutes a commitment, task, or follow-up.
3. For each action item, extract the owner (who said they would do it or was assigned it).
4. Extract deadlines, due dates, or time references ("by end of week", "before the board meeting").
5. Classify each item by urgency and type.
6. Produce a structured action list following the output standard below.
7. Update the project `next-actions.md` file with new items, avoiding duplicates.

## Working Rules

- Only extract genuine commitments. Distinguish between "I will do X" (action item) and "we should consider X" (suggestion, not an action item).
- If the owner is ambiguous, mark it as unassigned and note the surrounding context.
- Convert relative time references to absolute dates when the message date is known. If the message date is unknown, preserve the relative reference.
- Do not invent deadlines. If none was stated, record the deadline as "not specified".
- When updating `next-actions.md`, preserve existing items. Append new items with today's date as the extraction date.
- If an action item duplicates or supersedes an existing item in `next-actions.md`, note the update rather than creating a duplicate.
- Flag any action items that depend on another item being completed first.
- For meeting transcripts, pay attention to wrap-up and closing sections where action items are often restated.

## Output Standard

Each action item must contain these fields:

- **Action**: clear description of what needs to be done, stated as an imperative.
- **Owner**: the person responsible, by name.
- **Due date**: absolute date, relative reference, or "not specified".
- **Source**: where the commitment was made (message timestamp, transcript section).
- **Dependencies**: other items that must complete first, if any.
- **Status**: new, in-progress, or done (default to new for freshly extracted items).

Group action items by owner when presenting the list. Sort each owner's items by due date, with unspecified dates last.

When updating `next-actions.md`, use a consistent format so the file remains machine-readable and easy to scan.
