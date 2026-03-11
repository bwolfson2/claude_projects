---
description: Generate an investment-committee-ready memo for a company with evidence-backed recommendation
argument-hint: "<company name>"
---

# /write-memo

> Produce a partner-ready investment memo from all available diligence findings.

Write an IC memo for: $ARGUMENTS

## Execution

### Step 1: Gather All Available Evidence

Pull from every source for this company:

1. **Deal record** — `fund/crm/deals.json` for stage, status, round details
2. **Company workspace** — `fund/companies/{slug}/` for company.md, ic-snapshot.md, meeting notes
3. **Dataroom extractions** — query_documents.py for structured findings (cap table, financials, legal terms)
4. **Classified messages** — Recent emails, Slack threads, meeting transcripts tagged to this deal
5. **Research notes** — Any web-researcher or source-analyst outputs

```bash
# Check what dataroom extractions exist
python skills/document-processor/scripts/query_documents.py \
  --dataroom $(echo "$ARGUMENTS" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')_dataroom --stats 2>/dev/null

# Check company workspace
ls fund/companies/$(echo "$ARGUMENTS" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')/ 2>/dev/null
```

### Step 2: Identify Gaps

Before writing, flag what's missing:
- [ ] Commercial diligence findings
- [ ] Financial model / metrics review
- [ ] Technical / product assessment
- [ ] Legal review (cap table, SAFEs, contracts)
- [ ] Reference checks / customer calls
- [ ] Competitive landscape analysis

Note gaps explicitly in the memo.

### Step 3: Generate Memo

Use the diligence-memo-writer skill and investment-committee-memo-template to produce:

```markdown
# Investment Memo: [Company]

**Date:** [today]
**Author:** [fund name]
**Stage:** [Seed/A/B] | **Ask:** [$amount]
**Recommendation:** [INVEST / PASS / MORE DILIGENCE NEEDED]

## Executive Summary
[3-5 sentences: what they do, why now, what we think]

## Company Overview
[Business model, market, traction, team]

## Investment Thesis
1. [Thesis point 1 — with evidence]
2. [Thesis point 2 — with evidence]
3. [Thesis point 3 — with evidence]

## Key Risks
| Risk | Severity | Mitigation | Evidence |
|------|----------|------------|----------|
| [risk] | High/Med/Low | [how to mitigate] | [source] |

## Financial Analysis
[Revenue, burn, runway, unit economics — from dataroom extractions]

## Competitive Landscape
[Key competitors, differentiation, defensibility]

## Deal Terms
[Valuation, instrument, key terms from SAFE/term sheet extractions]

## Diligence Gaps
[What we still don't know and how to find out]

## Decision-Critical Questions
1. [Question that could change the recommendation]
2. [Question]

## Appendix
- Sources consulted
- Dataroom file inventory
- Meeting log
```

### Step 4: Save Output

Save the memo to `fund/companies/{slug}/diligence/ic-memo.md`

## Related Skills

- **diligence-memo-writer** — Core memo generation logic
- **finance-legal-diligence** — Financial and legal findings
- **commercial-diligence-review** — Commercial quality assessment
- **product-technical-diligence** — Technical evaluation
- **document-processor** — Dataroom extraction queries
