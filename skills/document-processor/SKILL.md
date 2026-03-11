---
name: document-processor
description: Extract text from dataroom documents (PDFs, spreadsheets, presentations) and run conversation-driven RLM-style extraction using Claude Code's own reasoning. Use when dataroom-intake has produced a manifest and specialist reviewers need structured access to document content without manual reading.
---

# Document Processor

Extract text from dataroom files and run RLM-style recursive extraction using Claude Code's own reasoning to produce structured, queryable results for specialist review skills.

## Core Workflow

1. Run `$dataroom-intake` first to get a manifest with file categories.
2. Run text extraction to populate `document_pages` (no LLM calls needed):
   ```bash
   python skills/document-processor/scripts/extract_text.py /path/to/dataroom --slug dataroom_slug
   ```
3. Use `process_document.py` subcommands to inspect and extract structured data from each file. Claude Code drives this with its own reasoning — no API key needed.
4. Specialist skills query results via `query_documents.py`.

## How RLM Processing Works (Conversation-Driven)

Instead of calling the Anthropic API directly, Claude Code uses its own conversation context to drive document analysis. The `process_document.py` script provides subcommands that act as the "symbolic handle" into the document:

### Step-by-step for each file:

1. **Get metadata**: `python process_document.py info --file X --dataroom Y`
   - Returns page count, char stats per page, extraction methods, TOC labels
2. **Read relevant pages**: `python process_document.py slice --file X --dataroom Y --pages 1-3`
   - Returns full text for the specified page range
3. **Search for terms**: `python process_document.py search --file X --dataroom Y --query "valuation"`
   - Returns matching pages with context snippets
4. **Get extraction schema**: `python process_document.py tasks --category governance`
   - Returns predefined extraction tasks and JSON schemas for the category
5. **Store result**: `python process_document.py store --file X --dataroom Y --key safe_terms --content '{"valuation_cap": "8000000", ...}'`
   - Saves structured extraction to `document_extractions` table

### Benefits over direct API calls:
- No ANTHROPIC_API_KEY needed in shell environment
- Claude Code uses its full reasoning capability with conversation context
- Natural iterative exploration — read metadata, slice relevant pages, extract
- Zero additional cost beyond the Claude Code session

## Scripts

- `scripts/extract_text.py` — Extract text from files (PDF, XLSX, PPTX, ZIP, text)
  - `--slug <dataroom_slug>` — Identifier for the dataroom
  - `--dry-run` — Preview without extracting
  - Handles native PDF text + OCR fallback for scanned pages

- `scripts/process_document.py` — RLM document access CLI (subcommands):
  - `info --file X --dataroom Y` — Document metadata, page stats, TOC
  - `slice --file X --dataroom Y --pages 1-3` — Text content for page range
  - `search --file X --dataroom Y --query "term"` — Search pages with snippets
  - `tasks [--category name]` — List predefined extraction tasks and schemas
  - `store --file X --dataroom Y --key K --content '{...}'` — Save structured extraction
  - `list-files --dataroom Y` — List all extracted files in a dataroom

- `scripts/process_dataroom.py` — Batch text extraction for entire dataroom
  - `--path <dir>` — Dataroom directory
  - `--slug <name>` — Dataroom slug
  - `--dry-run` — Preview plan
  - `--manifest <path>` — Use existing manifest from dataroom-intake

- `scripts/query_documents.py` — Query extracted content
  - `--dataroom <slug>` — Dataroom slug
  - `--type <extraction_type>` — Filter by type
  - `--key <extraction_key>` — Filter by key (e.g. "revenue_metrics")
  - `--search <query>` — Full-text search across pages
  - `--file <path> --pages 1-5` — Get raw text for specific pages
  - `--stats` — Processing statistics

## Predefined Extraction Tasks

Tasks are auto-selected based on `build_manifest.py` category:

| Category | Extractions |
|----------|------------|
| governance | cap_table, safe_terms |
| finance | revenue_metrics, pnl_summary, runway |
| legal | parties, key_terms |
| commercial | customer_list, gtm_metrics |
| product_technical | tech_stack, roadmap |

## Database Tables

- `document_pages` — Raw extracted text per page (the symbolic handle)
- `document_extractions` — Structured extraction results
- `document_jobs` — Processing job dedup and progress tracking

## Working Rules

- Always run text extraction before RLM processing.
- Process finance and legal documents first (highest DD value).
- Skip already-extracted files (dedup on UNIQUE constraint).
- Use `--dry-run` before committing to full dataroom processing.
- Store all results in SQLite with `PRAGMA journal_mode=OFF` (GDrive compatibility).
- Use the info→slice→search→store workflow to explore documents iteratively.
