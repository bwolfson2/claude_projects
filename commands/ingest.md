---
description: Point Claude at any URL, folder, or Google Drive link and have it ingested, classified, and routed to the right project
argument-hint: "<url, folder path, or Google Drive link>"
---

# /ingest

> Feed in any data source — files, URLs, Drive folders — and have it sorted automatically.

Ingest this: $ARGUMENTS

## Execution

### Step 1: Detect Source Type

Parse `$ARGUMENTS` to determine the source type:

| Pattern | Source Type | Handler |
|---------|-----------|---------|
| `https://drive.google.com/...` | Google Drive folder/file | Google Drive MCP or download |
| `https://www.dropbox.com/...` | Dropbox link | Download via URL |
| `https://...` (other URL) | Web page or file URL | WebFetch or download |
| `/path/to/folder` or `~/...` | Local folder | Direct filesystem access |
| `/path/to/file.pdf` etc. | Single local file | Direct filesystem access |

### Step 2: Handle by Source Type

#### Google Drive Folder
1. Use Google Drive MCP connector (if connected) to list files
2. Download files to a temp staging area: `fund/inbox/file_intake/{date}-{slug}/`
3. Proceed to classification

#### Google Drive / Dropbox / URL (single file)
1. Download file to `fund/inbox/file_intake/{date}-{slug}/`
2. Proceed to classification

#### Web URL (not a file)
1. Fetch page content using WebFetch
2. Save as markdown to `fund/inbox/file_intake/{date}-{slug}/page.md`
3. Index as a web scrape in the messages table
4. Proceed to classification

#### Local Folder
1. Inventory all files in the folder
2. Classify the folder type:
   - Contains PDFs/XLSX/PPTX with deal-related names → likely a **dataroom**
   - Contains .eml or .msg files → likely **email exports**
   - Contains .md or .txt files → likely **notes/research**
   - Mixed → inventory and ask user

#### Local File
1. Identify file type by extension
2. Route accordingly (PDF → document-processor, XLSX → document-processor, etc.)

### Step 3: Classify Content

Determine which deal or project this content belongs to:

```bash
# If it looks like a dataroom, run intake
python skills/dataroom-intake/scripts/build_manifest.py <staging_path>

# Run classification on any text content
python skills/deal-project-classifier/scripts/classify_messages.py
```

**Classification signals:**
- Filename contains a company name → match to deal
- Folder name contains a company name → match to deal
- Content mentions a known company → match to deal
- URL domain matches a known company → match to deal
- No match → ask user or create new deal/project

### Step 4: Route to Workflow

Based on classification:

| Content Type | Action |
|-------------|--------|
| Dataroom folder | → `dataroom-intake` → `document-processor` → update deal stage |
| Single document | → `document-processor` extract text → classify → store |
| Email exports | → `message-ingestion` → `classify` → `apply_updates` |
| Web page | → `source-analyst` → attach findings to project |
| Research/notes | → Index in messages table → classify → attach to project |

### Step 5: Report

```markdown
# Ingestion Report

**Source:** [URL/path]
**Files Found:** [count]
**Classified To:** [deal/project name] (confidence: [score])

## Files Processed
| File | Type | Size | Status |
|------|------|------|--------|
| [name] | PDF | 2.1MB | ✅ Extracted (45 pages) |
| [name] | XLSX | 340KB | ✅ Extracted (3 sheets) |

## Actions Taken
- [Created dataroom workspace for CompanyX]
- [Extracted text from 12 documents]
- [Updated deal stage to dataroom_received]

## Needs Attention
- [File could not be processed: reason]
- [Classification uncertain: please confirm project]
```

## Related Skills

- **dataroom-intake** — Dataroom inventory and categorization
- **document-processor** — Text extraction and RLM analysis
- **message-ingestion** — Message storage
- **deal-project-classifier** — Content classification
- **reactive-router** — Workflow dispatch
