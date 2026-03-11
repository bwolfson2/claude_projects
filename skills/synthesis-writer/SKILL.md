---
name: synthesis-writer
description: Combine findings from multiple source analyses into a coherent research report. Use when synthesizing research findings into a final deliverable.
---

# Synthesis Writer

Combine source-level findings into a coherent research report. The goal is to produce a deliverable that a decision-maker can act on without reading the underlying sources.

## Workflow

1. Read all source analyses in `projects/research/{slug}/sources/`.
2. Inventory the evidence: list every key finding and data point across sources.
3. Identify themes, patterns, agreements, and contradictions.
4. Organize findings into a logical narrative structure.
5. Write the report following the output standard below.
6. Save output to `projects/research/{slug}/outputs/report.md`.

## Working Rules

- Ground every claim in at least one source analysis. Use inline citations referencing the source slug.
- When sources disagree, present both positions and state which has stronger evidence.
- Do not introduce claims that are not supported by the analyzed sources.
- Distinguish between well-evidenced conclusions and tentative inferences. Label confidence level (high, medium, low) for each major conclusion.
- Lead with the most important findings. Busy readers may stop after the executive summary.
- Keep prose concise. Prefer short paragraphs and bullet lists over long narrative blocks.
- If critical questions remain unanswered, state them explicitly in the gaps section rather than glossing over them.
- Quantitative claims must carry their original units and context. Do not round or convert without noting the original figure.

## Output Standard

Each synthesis report must contain these sections:

- **Executive summary**: three to five sentences capturing the most important conclusions.
- **Key findings**: the major themes and conclusions, each with supporting evidence and confidence level.
- **Evidence map**: a brief table or list mapping each conclusion to its supporting sources.
- **Contradictions and tensions**: where sources disagree and which interpretation is better supported.
- **Gaps and open questions**: what the research did not resolve and what additional sources would help.
- **Methodology note**: how many sources were analyzed, what types, and any coverage limitations.
- **Appendix: source list**: full list of source slugs with one-line descriptions.

If the research question was provided, restate it at the top of the report and answer it directly in the executive summary.
