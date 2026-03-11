---
description: Extract text from dataroom documents and run structured extraction using RLM-style processing
argument-hint: "<dataroom path or slug>"
---

# /process-dataroom

> Process a startup's dataroom — extract text, run structured analysis, and make content queryable.

Process this dataroom: $ARGUMENTS

## Execution

### Phase 1: Text Extraction (no LLM cost)

1. **Extract text** from all documents in the dataroom:
   ```bash
   python skills/document-processor/scripts/extract_text.py \
     <dataroom_path> --slug <dataroom_slug>
   ```

2. Review extraction stats — page counts, character counts, any unsupported files.

### Phase 2: RLM-Style Document Processing

For each key document, use the conversation-driven RLM workflow:

1. **Get document info:**
   ```bash
   python skills/document-processor/scripts/process_document.py \
     info --file <file> --dataroom <slug>
   ```

2. **Slice into relevant pages** based on what you find:
   ```bash
   python skills/document-processor/scripts/process_document.py \
     slice --file <file> --dataroom <slug> --pages <range>
   ```

3. **Search for specific terms:**
   ```bash
   python skills/document-processor/scripts/process_document.py \
     search --file <file> --dataroom <slug> --query "<term>"
   ```

4. **Store structured extractions:**
   ```bash
   python skills/document-processor/scripts/process_document.py \
     store --file <file> --dataroom <slug> --key <extraction_key> \
     --content '<json>'
   ```

### Phase 3: Query & Report

```bash
python skills/document-processor/scripts/query_documents.py \
  --dataroom <slug> --stats
```

Present a summary of what was extracted and any gaps found.

## Related Skills

- **document-processor** — The underlying RLM extraction engine
- **dataroom-intake** — File inventory and categorization (run first)
- **startup-diligence-orchestrator** — Full diligence workflow
