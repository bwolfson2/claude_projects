# Routing Rules Reference

## Detection Patterns

### Dataroom Received
**Keywords (subject + body):** dataroom, data room, diligence materials, documents attached, shared folder, drive link, dropbox link, files for review
**Attachments:** .zip, .pdf (multiple), .xlsx + any of the above keywords
**Confidence boost:** Sender domain matches an active deal's company domain

### Term Sheet / Legal Document
**Keywords:** term sheet, SAFE agreement, safe note, side letter, convertible note, subscription agreement, shareholders agreement, stock purchase, option grant, board consent
**Attachments:** .pdf or .docx with legal keywords in filename
**Priority:** Always URGENT — these are time-sensitive

### Meeting Request
**Keywords:** schedule, meeting, call, sync, catch up, coffee chat, let's connect, free this week, calendar invite, would love to chat
**Attachments:** .ics files
**Context:** Often combined with an intro or follow-up route

### New Introduction
**Keywords:** introducing, intro, meet, connect you with, wanted to introduce, thought you should meet, passing along
**Sender patterns:** Typically from a known contact introducing an unknown party
**Domain check:** Recipient domain not in existing deals → likely new deal

### Funding Announcement
**Keywords:** raised, funding, series, round, closed, pre-seed, seed, venture, capital
**Context:** Usually in newsletters, forwarded announcements, or direct founder updates

### Action Items
**Patterns:** "I will", "we'll send", "by Friday", "next week", "action item", "follow up on", "please send", "can you", "deadline"
**Extraction:** Owner + due date + task description

### Follow-up / Thread Reply
**Detection:** Re: or Fwd: prefix, or message references an existing thread_id
**Action:** Update last_touch, check for stage-changing content

## Priority Levels

| Priority | Response Time | User Confirmation |
|----------|--------------|-------------------|
| URGENT | Immediate notification | Always confirm before acting |
| HIGH | Act within current monitor sweep | Confirm for destructive actions |
| MEDIUM | Queue for next sweep | Auto-execute, report in summary |
| LOW | Batch process | Auto-execute silently |

## Conflict Resolution

When a message matches multiple routes:
1. Highest priority wins
2. If same priority, most specific route wins (term_sheet > dataroom > meeting)
3. All matched routes are logged in the action plan
4. Secondary actions can be queued for follow-up
