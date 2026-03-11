---
name: dataroom-intake
description: Inventory startup dataroom folders, normalize messy file sets, infer likely diligence categories, and identify missing documents before specialist review begins. Use when Codex receives a folder of mixed documents such as PDFs, spreadsheets, exports, decks, contracts, data dumps, or nested archives and needs to stage a structured diligence workspace.
---

# Dataroom Intake

Start every diligence run with a manifest. The intake step determines what exists, what looks important, and what is missing before deeper analysis starts.

## Workflow

1. Run `scripts/build_manifest.py` against the dataroom root.
2. Review the generated counts, categories, and keyword signals.
3. Flag missing core materials using `references/file-handling.md`.
4. Create a staged review workspace using `assets/diligence-workspace-template.md`.
5. Hand the manifest plus missing-items list to the orchestrator.

## Missing Document Heuristics

Treat these as common expected inputs, not absolute requirements:

- investor deck or company overview
- historical financials and current budget or forecast
- KPI or board reporting pack
- cap table and financing documents
- major customer contracts or customer list
- product roadmap and architecture or security material
- legal entity, IP, employment, and compliance documents

## Output Standard

Produce:

- a dataroom manifest
- a category summary
- a likely-high-value file shortlist
- a missing-documents list
- any extraction blockers such as unreadable scans, password protection, or unsupported formats

Read `references/file-handling.md` for categorization and fallback rules.
