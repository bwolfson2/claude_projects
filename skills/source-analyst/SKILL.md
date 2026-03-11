---
name: source-analyst
description: Read and extract key findings from individual research sources, producing structured source summaries with citations. Use when analyzing a specific document or web source for a research project.
---

# Source Analyst

Extract structured findings from a single research source. Prioritize concrete data points, direct quotes, and falsifiable claims over general narrative.

## Workflow

1. Read the source document or fetch the URL provided.
2. Identify the source type (academic paper, news article, industry report, company filing, interview transcript, etc.).
3. Extract key findings, data points, and notable quotes.
4. Assess source credibility and note any conflicts of interest or methodological limitations.
5. Produce a structured summary following the output standard below.
6. Save output to `projects/research/{slug}/sources/{source-slug}.md`.

## Working Rules

- Every extracted claim must include a citation with page number, section, or paragraph reference.
- Distinguish between primary data (original research, firsthand accounts) and secondary data (aggregated, reported, or interpreted).
- If the source makes quantitative claims without methodology disclosure, flag them as unverified.
- Record the publication date and author credentials when available; mark them unknown otherwise.
- Do not editorialize or inject opinion. Summarize what the source says, not what you think about it.
- If the source contradicts findings from other sources already in the project, note the contradiction explicitly.
- Prefer extracting direct quotes for controversial or load-bearing claims.
- Limit each source summary to the most important findings. Aim for signal density, not completeness.

## Output Standard

Each source summary must contain these sections:

- **Source metadata**: title, author, date, URL or file path, source type.
- **Key findings**: numbered list of the most important claims or data points, each with a citation.
- **Notable quotes**: direct quotes that capture critical arguments or evidence (maximum five).
- **Data points**: any quantitative figures, statistics, or metrics worth preserving.
- **Credibility notes**: author authority, methodology quality, potential bias, conflicts of interest.
- **Open questions**: anything the source raises but does not resolve.
- **Tags**: subject-matter tags for cross-referencing with other sources.

When the source is a web page, record the access date alongside the URL.
