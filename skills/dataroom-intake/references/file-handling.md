# File Handling Guide

## Category Hints

- `Commercial`: decks, CRM exports, customer lists, pipeline reports, marketing plans, win/loss notes
- `Finance`: historical P&L, balance sheet, cash flow, forecast, KPI pack, ARR or MRR analysis
- `Legal`: contracts, NDAs, service terms, privacy documents, corporate formation, IP assignments
- `Product and technical`: architecture diagrams, roadmap, security docs, engineering metrics, APIs
- `Governance`: board materials, cap table, SAFEs, notes, option plans, financing docs

## Intake Rules

- Prefer relative paths in manifests so later agents can cite them directly.
- Keep nested folder names because they often encode the company's intended taxonomy.
- Flag archives because they often hide high-value files that need separate extraction.
- Flag images and scans when they likely contain documents that will need OCR.
- Flag unusually tiny spreadsheets or decks because they are often placeholders, not source material.

## Missing Inputs Checklist

Ask for follow-up if the dataroom lacks most of these:

- deck or board update
- financial statements
- forecast or budget
- KPI or revenue cohort file
- cap table
- customer evidence
- roadmap or technical architecture
- legal agreements
