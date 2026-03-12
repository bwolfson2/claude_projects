# Sheet Structure Reference

## Tab: "DD Pipeline"

| Column | JSON Source | Format |
|--------|-----------|--------|
| Company | `company_name` | Text |
| Stage | `stage` | Color-coded: sourced=gray, intro=blue, diligence=yellow, ic=orange, terms=green, closed=dark green, passed=red |
| Status | `status` | active/paused/passed |
| Priority | `priority` | P0/P1/P2/P3 |
| Sector | `sector` | Text |
| Round | `round` | Text |
| Raise ($) | `raise_usd` | Currency |
| Val Cap ($) | `valuation_cap_usd` | Currency |
| Decision | `decision_posture` | Text |
| Owner | `owner` | Text |
| Last Touch | `last_touch` | Date (YYYY-MM-DD) |
| Next Action | `next_action` | Text |
| Due Date | `next_action_due` | Date, red if overdue |
| Docs Uploaded | Count from `document_pages` | Number |
| Dataroom Link | `artifacts.dataroom` | Hyperlink |
| Commercial DD | `diligence.commercial` | Status emoji |
| Product/Tech DD | `diligence.product_technical` | Status emoji |
| Finance/Legal DD | `diligence.finance_legal` | Status emoji |
| Memo DD | `diligence.memo` | Status emoji |
| Memo Link | `artifacts.short_memo` | Hyperlink |
| Terms | `terms_summary` | Text |
| Thesis | `thesis` | Truncated to 200 chars |
| Comments | `comments` | Free text |

## Diligence Status Mapping

| Value | Display |
|-------|---------|
| complete | Done |
| in_progress | In Progress |
| pending | Pending |
| not_started | Not Started |
| blocked | Blocked |

## Tab: "Projects"

| Column | JSON Source | Format |
|--------|-----------|--------|
| Name | `project_name` | Text |
| Type | `project_type` | Text |
| Category | `category` | Text |
| Status | `status` | Text |
| Priority | `priority` | Text |
| Owner | `owner` | Text |
| Created | `created` | Date |
| Last Updated | `last_updated` | Date |
| Description | `description` | Truncated to 200 chars |
| Next Action | `next_action` | Text |

## Tab: "CRM Contacts"

| Column | DB/JSON Source | Format |
|--------|--------------|--------|
| Name | `name` | Text |
| Email | `email` | Text |
| Company | `company` | Text |
| Role/Title | `title` | Text |
| Phone | `phone` | Text |
| Slack | `slack_handle` | Text |
| WhatsApp | `whatsapp_id` | Text |
| Signal | `signal_id` | Text |
| LinkedIn | `linkedin_url` | Hyperlink |
| Tags | `tags` | Comma-separated |
| Last Contacted | `last_contacted` | Date |
| Source | `source` | Text |
| Context | `context` | Text |
| Related Deals | `deal_slugs` | Comma-separated |
| Related Projects | `project_slugs` | Comma-separated |

## Per-Deal Tabs: "DD: {Company}"

Layout (rows, not columns):
1. **Header block:** Company, Stage, Round, Valuation, Decision, Owner
2. **Diligence Progress:** 4 tracks (Commercial, Product/Tech, Finance/Legal, Memo) with status + key findings
3. **Recent Activity:** Last 10 messages (date, source, summary)
4. **Key Findings:** Top extractions from dataroom
5. **Open Questions:** Full list
6. **Action Items:** From next-actions
7. **Contacts Involved:** People linked to this deal

## Per-Project Tabs: "Proj: {Project}"

Layout (rows):
1. **Header block:** Name, Type, Category, Owner, Created, Last Updated
2. **Status & Description**
3. **Recent Activity:** Last 10 messages
4. **Action Items**
5. **Assets/Docs:** File links
6. **Contacts Involved**

## Conditional Formatting Rules

| Rule | Applies To | Condition | Format |
|------|-----------|-----------|--------|
| Overdue | Due Date column | Date < today AND status != passed | Red background |
| Active deal | Status column | "active" | Green text |
| Paused deal | Status column | "paused" | Orange text |
| Passed deal | Status column | "passed" | Gray text, strikethrough |
| High priority | Priority column | "P0" or "P1" | Bold |
