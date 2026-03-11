# RLM Prompt Templates

## System Prompt (Document Analysis Agent)

Used in `process_document.py` as `RLM_SYSTEM_PROMPT`. Gives the LLM programmatic
access to document content without loading the full document into context.

### Design Principles (from MIT CSAIL RLM paper)

1. **Symbolic Handle**: Document stored externally, accessed via function calls
2. **Metadata-Only Context**: LLM sees page counts, TOC, char stats — not full text
3. **Model-Driven Chunking**: The LLM decides which pages to request, not hardcoded
4. **State Accumulation**: Results stored in extraction records, not autoregressive output
5. **Cost-Efficient Recursion**: Cheap models for simple extraction, expensive models for reasoning

### Command Reference

| Command | Args | Returns |
|---------|------|---------|
| `SLICE(start, end)` | 1-indexed page range (inclusive) | Full text of requested pages |
| `SEARCH("query")` | Keyword or phrase | Page numbers + 200-char snippets |
| `DONE(result)` | JSON object matching schema | Terminates loop, stores extraction |

### Effective Patterns

**Pattern A: TOC-Guided Navigation**
```
1. Review TOC to identify relevant sections
2. SLICE the most promising section
3. DONE with extracted data
```

**Pattern B: Search-First Discovery**
```
1. SEARCH for key terms (e.g., "revenue", "valuation cap")
2. SLICE pages with matches
3. DONE with structured extraction
```

**Pattern C: Progressive Narrowing**
```
1. SLICE first 2-3 pages for document overview
2. SEARCH for specific data points
3. SLICE targeted pages
4. DONE with combined results
```

### Cost Optimization

- Always SEARCH before SLICE when looking for specific data
- Request minimal page ranges (1-3 pages vs entire document)
- Use predefined extraction schemas to avoid open-ended exploration
- Haiku handles simple extraction (entities, dates, numbers)
- Sonnet handles reasoning (financial analysis, legal interpretation)
