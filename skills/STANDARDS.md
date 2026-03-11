# Cross-Skill Standards

Shared conventions for all diligence and project management skills. Every specialist skill and orchestrator must follow these standards.

## Citation Format

All evidence references must use this format:

```
[Source Type] File: <relative path> | Page/Section: <location> | Confidence: <high|medium|low>
```

Examples:
- `[Financial] File: midbound_dataroom/Financials/midbound financials.xlsx | Sheet: P&L | Confidence: high`
- `[Legal] File: midbound_dataroom/Legal/Articles of Incorporation/MeetVisitors_ Inc. Certificate of Incorporation.pdf | Page: 1 | Confidence: high`
- `[Verbal] Source: Founder call 2026-03-05 | Notes: fund/companies/midbound/meetings/notes.md | Confidence: medium`
- `[Email] File: fund/inbox/2026-03/subject-slug/email.md | From: sender@domain.com | Date: YYYY-MM-DD | Confidence: high`
- `[Transcript] File: fund/transcripts/2026-03/meeting-slug.md | Participants: names | Date: YYYY-MM-DD | Confidence: medium`

## Severity Thresholds

### Critical (blocks investment decision)
- Customer concentration: single customer >40% of revenue
- Runway: <3 months without new funding
- Legal: unresolved IP ownership, active litigation, missing incorporation docs
- Security: data breach history, no encryption at rest, PII exposure
- Cap table: missing instruments, unaccounted dilution >10%

### High (materially affects terms or conviction)
- Customer concentration: top 3 customers >60% of revenue
- Runway: <6 months without new funding
- Churn: logo churn >15% annually or NRR <90%
- Security: no pentest completed, no SOC2 or equivalent
- Key-person: single engineer owns >50% of codebase
- Forecast: hiring plan unfunded beyond 6 months

### Medium (worth noting, manageable)
- Customer concentration: top 5 customers >50% of revenue
- Implementation: >20% of ACV spent on onboarding per customer
- Roadmap: >50% of roadmap items lack staffing assignment
- Contracts: standard terms with non-standard carve-outs

### Low (informational)
- Minor documentation gaps
- Non-standard but common legal structures
- Cosmetic product issues
- Industry-standard vendor dependencies

## Evidence Quality

- **Fully Supported**: Claim backed by primary source document (financial statement, signed contract, audit report)
- **Partially Supported**: Claim backed by secondary source (deck, verbal confirmation) or primary source is incomplete
- **Unsupported**: Claim made without documentary evidence; requires follow-up

## Process Gates

### Gate 1: Intake → Specialist Review
Exit criteria: Dataroom manifest complete, missing docs list generated, scope questions defined.

### Gate 2: Specialist Review → Synthesis
Exit criteria: All three specialist reviews (commercial, product/tech, finance/legal) have at least a draft with risk tables. Any "Critical" severity items flagged to lead reviewer.

### Gate 3: Synthesis → IC Memo
Exit criteria: Risk register consolidated (no duplicates), decision-critical questions listed, recommendation drafted.

### Gate 4: IC Memo → Decision
Exit criteria: Memo reviewed by at least one partner, open questions either answered or explicitly accepted as risks.

## Conflict Resolution

When specialists disagree on the same evidence:
1. Flag the disagreement explicitly in the risk register
2. Present both interpretations with their reasoning
3. The memo writer decides which framing appears in the final memo, but must note the alternative view
4. If severity ratings differ by 2+ levels (e.g., Low vs. High), escalate to lead reviewer

## Sync Protocol

After any deal or project update:
1. Update the relevant JSON file (deals.json or projects.json)
2. Run the tracker-sync script to update VFT-Master-Tracker.xlsx
3. Google Drive for Desktop auto-syncs the xlsx to Drive
4. If edits happen in Google Sheets, run reverse sync before the next local update
