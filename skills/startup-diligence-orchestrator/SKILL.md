---
name: startup-diligence-orchestrator
description: Coordinate full startup due diligence across dataroom folders, mixed document sets, and specialist review tracks. Use when Codex needs to run an end-to-end diligence process for a startup company, break work into sub-agents, route files to the right specialty reviewer, maintain an evidence-backed risk register, and synthesize outputs into a partner-ready summary or investment memo.
---

# Startup Diligence Orchestrator

Run the diligence process as a coordinator, not as a single monolithic reviewer. Set scope, assign specialist review tracks, maintain evidence quality, and merge findings into one decision-ready narrative.

## Core Workflow

1. Inspect the dataroom folder layout and produce an inventory first.
2. Run `$document-processor` to extract text and structured data from all dataroom files (PDFs, spreadsheets, presentations). This makes document content queryable for all downstream specialist skills.
3. Build a review plan by domain: commercial, product/technical, finance/legal, and open questions.
4. Route work to the relevant specialist skills instead of keeping all analysis in one thread.
5. Maintain a shared evidence log with file-path citations, page numbers when available, and confidence levels.
6. Synthesize findings into an investment view, red flags, upside cases, and a diligence question list.
7. If the repo is using fund deal tracking, sync the resulting memo, posture, and next actions into `$fund-dealflow-orchestrator`.

Read `references/workflow.md` for the operating sequence, `references/subagents.md` for delegation rules, and `references/prompt-recipes.md` for reusable invocation prompts.

## Working Rules

- Treat every material claim as either `supported`, `partially supported`, or `unsupported`.
- Prefer direct evidence from dataroom files over management assertions, summaries, or marketing decks.
- Separate facts, inferences, and missing evidence explicitly.
- Record contradictions instead of averaging them away.
- Escalate gaps in core areas: revenue quality, customer concentration, churn, pipeline credibility, product reliability, security posture, legal exposure, and fundraising dependency.
- If a domain lacks evidence, say that diligence is incomplete and specify the missing documents.

## Delegation Map

- Use `$dataroom-intake` first for inventory, categorization, and workspace setup.
- Use `$document-processor` after intake to extract text and run structured extractions (revenue metrics, cap tables, contract terms, etc.). This replaces manual document reading for specialist skills.
- Use `$commercial-diligence-review` for market, customers, GTM, traction, and competitive posture.
- Use `$product-technical-diligence` for roadmap, engineering quality, delivery risk, security signals, and product differentiation.
- Use `$finance-legal-diligence` for financial quality, legal exposure, cap table, contracts, and compliance signals.
- Use `$diligence-memo-writer` after the specialist passes are complete.
- Use `$fund-dealflow-orchestrator` when the diligence result needs to update the fund CRM or per-company workspace.

## Output Standard

Always aim to produce these artifacts:

- An inventory summary of what the dataroom contains and what is missing.
- A prioritized risk register with severity and evidence.
- A list of diligence questions that would change the underwriting decision.
- A concise recommendation: `lean in`, `proceed with caution`, or `do not advance`.

Use `assets/diligence-report-template.md` when drafting the final integrated report.
