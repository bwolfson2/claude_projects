# Field Mapping Reference

This document defines the exact mapping between JSON fields and Excel columns for both the DD Pipeline and Project Management tabs.

## DD Pipeline Tab

Maps `deals.json` company records to the DD Pipeline worksheet.

| Excel Column | Column Letter | JSON Field | Type | Notes |
|---|---|---|---|---|
| Company | A | `company_name` | string | Full company name |
| Stage | B | `stage` | string | From stages.md (e.g., "sourcing", "intro_call", "deep_dd", "ic_prep", "ic_ready", "term_sheet", "portfolio") |
| Status | C | `status` | string | "active", "paused", "passed", "invested" |
| Decision Posture | D | `decision_posture` | string | e.g., "lean_yes_assumption_based", "lean_no", "pass", "needs_more_info" |
| Sector | E | `sector` | string | Industry/market description |
| Round | F | `round` | string | e.g., "Pre-seed SAFE", "Seed", "Series A" |
| Raise ($) | G | `raise_usd` | number | Formatted as currency |
| Val Cap ($) | H | `valuation_cap_usd` | number | For SAFEs; formatted as currency |
| Owner | I | `owner` | string | Person responsible (e.g., "fund", name) |
| Priority | J | `priority` | string | "high", "medium", "low" |
| Last Touch | K | `last_touch` | date | YYYY-MM-DD format |
| Next Action | L | `next_action` | string | Prose description of what's next |
| Next Action Owner | M | `next_action_owner` | string | Person/team responsible for next step |
| Due Date | N | `next_action_due` | date | YYYY-MM-DD format |
| Thesis | O | `thesis` | string | Investment thesis (can be multi-line) |
| Commercial DD | P | `diligence.commercial` | string | Status: "pending", "in_progress", "complete", "blocked" |
| Product/Tech DD | Q | `diligence.product_technical` | string | Status: "pending", "in_progress", "complete", "blocked" |
| Finance/Legal DD | R | `diligence.finance_legal` | string | Status: "pending", "in_progress", "complete", "blocked" |
| Memo | S | `diligence.memo` | string | Status: "pending", "in_progress", "complete", "blocked" |
| Open Questions | T | `open_questions` | array | Joined with line breaks (one per line) |
| Assumptions | U | `assumptions` | array | Joined with line breaks (one per line) |

### Notes on Formatting

- **Currency columns (G, H)**: Display as USD with 2 decimal places
- **Date columns (K, N)**: Display as YYYY-MM-DD
- **Array columns (T, U)**: Array items joined with newlines (Excel multi-line cells)
- **Diligence status**: Use text representation, not codes

## Project Management Tab

Maps `projects.json` records to the Project Management worksheet.

| Excel Column | Column Letter | JSON Field | Type | Notes |
|---|---|---|---|---|
| Project | A | `name` | string | Project name |
| Category | B | `category` | string | "Operations", "Legal/Corp", "Product", "Finance", "Data/Analytics", etc. |
| Status | C | `status` | string | "not_started", "in_progress", "on_hold", "completed" |
| Priority | D | `priority` | string | "High", "Medium", "Low" |
| Owner | E | `owner` | string | Person responsible |
| Start Date | F | `start_date` | date | YYYY-MM-DD format |
| Target Date | G | `target_date` | date | YYYY-MM-DD format |
| Description | H | `description` | string | Project overview/scope |
| Next Action | I | `next_action` | string | Immediate next step |
| Next Action Owner | J | `next_action_owner` | string | Person/team for next step |
| Due Date | K | `next_action_due` | date | YYYY-MM-DD format |
| Docs/Links | L | `artifacts` or `links` | array or object | Joined links, one per line |
| Notes | M | `notes` | string | Additional context |

### Notes on Formatting

- **Date columns (F, G, K)**: Display as YYYY-MM-DD
- **Links column (L)**: If `artifacts` is an object, format as "name: url" one per line
- **Status values**: Use exact strings as defined (not codes)

## JSON Structure Reference

### deals.json Company Record

```json
{
  "slug": "midbound",
  "company_name": "Midbound, Inc.",
  "status": "active",
  "stage": "ic_prep",
  "owner": "fund",
  "source": "existing repo diligence",
  "sector": "B2B SaaS / visitor identification",
  "round": "Pre-seed SAFE",
  "raise_usd": 700000,
  "valuation_cap_usd": 5000000,
  "decision_posture": "lean_yes_assumption_based",
  "priority": "high",
  "last_touch": "2026-03-05",
  "next_action": "Obtain historical financials...",
  "next_action_owner": "fund",
  "next_action_due": "2026-03-16",
  "thesis": "SMB-friendly person-level website identification...",
  "open_questions": [
    "Historical financials, cash balance, and billing-grade revenue support.",
    "Completed penetration-test report and stronger security package."
  ],
  "assumptions": [
    "Lilian Cruanes returned shares were properly distributed...",
    "Midbound data accuracy is genuinely high..."
  ],
  "artifacts": {
    "company_workspace": "/path/to/workspace",
    "meeting_notes": "/path/to/notes.md",
    ...
  },
  "diligence": {
    "commercial": "complete",
    "product_technical": "complete",
    "finance_legal": "blocked",
    "memo": "complete"
  }
}
```

### projects.json Project Record (Expected Structure)

```json
{
  "id": "proj_001",
  "name": "Legal Documentation Review",
  "category": "Legal/Corp",
  "status": "in_progress",
  "priority": "High",
  "owner": "legal_team",
  "start_date": "2026-03-01",
  "target_date": "2026-03-31",
  "description": "Review and standardize legal documentation across all portfolio companies.",
  "next_action": "Draft template package",
  "next_action_owner": "jane_smith",
  "next_action_due": "2026-03-15",
  "artifacts": {
    "template_doc": "https://docs.google.com/document/d/...",
    "review_checklist": "https://..."
  },
  "notes": "In coordination with Finance team"
}
```

## Sync Logic Rules

1. **Empty/Null Handling**: If a JSON field is null or missing, the corresponding Excel cell is left blank.
2. **Array Joining**: Array fields are joined with newline characters (`\n`) for multi-line Excel cells.
3. **Object Serialization**:
   - For `diligence` object: extract only the four status fields (commercial, product_technical, finance_legal, memo)
   - For `artifacts` object: format as "name: value" one per line, or just use the values if not a mapping
4. **Date Format**: Always store/display as YYYY-MM-DD in both JSON and Excel
5. **Currency Format**: Numbers without decimal places in JSON should display with .00 in Excel
6. **Type Conversion**:
   - Numbers stay numbers
   - Strings stay strings
   - Arrays are joined into multi-line text
   - Objects are either extracted (diligence) or serialized (artifacts)

## Validation Rules

Before writing to Excel:
- Verify all required fields exist in the JSON (or use empty string as default)
- Ensure dates are valid YYYY-MM-DD format
- Ensure currency values are numeric
- Ensure arrays are not nested (flatten if needed)

## Missing Project Structure

If `projects.json` does not exist yet, the Project Management tab will remain empty (keep headers, clear data rows). The sync script will create the file structure when reverse-syncing data from Excel.
