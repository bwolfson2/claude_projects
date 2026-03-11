---
description: Connect to your calendar, review upcoming meetings, and auto-prep for calls with deal context
argument-hint: "[today | this week | prep <meeting>]"
---

# /calendar

> See what's coming up and get prepped for every meeting.

Calendar command: $ARGUMENTS

## Execution

### If "today" or no arguments: Today's Schedule

1. **Pull calendar events** via connected calendar MCP (Google Calendar, Outlook Calendar) or ask user to paste their schedule
2. For each meeting today:
   - Check if any attendee domain matches an active deal
   - Check if the meeting title references a known company/project
   - Flag meetings that need prep

```markdown
# Today's Calendar — [Date]

| Time | Meeting | Company/Project | Prep Status |
|------|---------|----------------|-------------|
| 10:00 | Call with Jane (Acme Corp) | 🔗 acme-corp (Deep Diligence) | ⚠️ Needs prep |
| 14:00 | Team standup | internal | ✅ No prep needed |
| 16:00 | Intro: Bob → WidgetCo | 🆕 New contact | ⚠️ Research needed |
```

### If "this week": Weekly Calendar Overview

Same as above but for the full week. Group by day. Highlight:
- Meetings with active deal companies
- New introductions
- Follow-up meetings (check if action items are pending)

### If "prep <meeting or company>": Meeting Prep

Deep prep for a specific meeting:

1. **Identify the company/deal** from the meeting title or attendees
2. **Pull deal context:**
   - Deal record from `fund/crm/deals.json`
   - Recent messages classified to this deal (last 30 days)
   - Dataroom extractions if available
   - Previous meeting notes from `fund/companies/{slug}/meetings/`
   - Open action items from `next-actions.md`

3. **Research attendees:**
   - Look up attendee names/emails
   - Web search for recent news about the company

4. **Generate prep brief:**

```markdown
# Meeting Prep: [Company] — [Meeting Type]

**When:** [date/time]
**Attendees:** [names + titles]
**Deal Stage:** [current stage]
**Last Touch:** [date + summary]

## Context
[What's happened with this deal so far — key points from messages, meetings, diligence]

## Attendee Profiles
### [Name] — [Title]
- [Background / relevant info]

## Open Items from Last Interaction
- [Action item — owner — status]

## Suggested Agenda
1. [Follow up on X from last meeting]
2. [Discuss Y based on recent email]
3. [Ask about Z]

## Questions to Ask
- [Question based on gaps in our knowledge]
- [Question based on recent news/changes]

## After the Meeting
- Update deal record with notes
- Extract action items
- Send follow-up email if needed
```

### Calendar Integration

**With Google Calendar MCP:**
- Automatically pull events
- Match attendee emails to deal contacts
- Create prep notes before meetings

**With Outlook Calendar MCP:**
- Same as above via Outlook connector

**Without calendar connector:**
- Ask user to paste their schedule or describe upcoming meetings
- Still provide full prep workflow

### Auto-Prep (via /watch)

When the `vft-monitor-sweep` scheduled task runs each morning, it should:
1. Check today's calendar for meetings with deal companies
2. Auto-generate prep briefs for any unprepped meetings
3. Include in the morning monitor report

## Related Skills

- **fund-dealflow-orchestrator** — Deal context
- **web-researcher** — Attendee and company research
- **action-extractor** — Open action items
- **thread-summarizer** — Recent conversation context
