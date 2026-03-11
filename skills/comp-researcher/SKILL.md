---
name: comp-researcher
description: Research compensation benchmarks for a role and market using web scraping. Use when determining salary ranges, equity packages, or benefits for a hiring project.
---

# Comp Researcher

Research compensation benchmarks for a specific role, level, and market. Scrape public salary data sources, normalize the results, and produce a comp summary the hiring lead can use to set offer ranges and negotiate competitively.

## Trigger Phrases

- "Research comp for this role"
- "What should we pay for a {role} in {market}?"
- "Pull salary benchmarks for {title}"
- "Get compensation data for the hiring project"
- "Look up equity ranges for {level} at {stage}"

## Prerequisites

- A hiring project should exist at `projects/hiring/{slug}/` with a `role.md` (recommended but not required).
- Claude in Chrome extension must be connected for web scraping.
- The `web-researcher` skill must be available for browser automation.

## Core Workflow

1. **Determine search parameters**
   - Read `projects/hiring/{slug}/role.md` if available for title, level, and location.
   - If no project exists, gather parameters from the user: role title, seniority level, market/location, company stage.
   - Normalize the title to common industry terms (e.g., "Senior Software Engineer", "Staff Designer").
   - Identify the company stage for equity benchmarking: seed, Series A, Series B, growth, public.

2. **Scrape compensation sources**
   - Use the `web-researcher` skill and Claude in Chrome to extract data from:
     - **Levels.fyi** -- base, stock, bonus by company and level
     - **Glassdoor** -- salary ranges and reported compensation
     - **Blind** -- anonymous comp-sharing threads (search for role + level)
     - **Pave** -- if accessible, benchmark data by stage and role
   - For each source, extract: title matched, level matched, base range, equity range, bonus range, total comp range, sample size where available.
   - Handle paywalls and login walls per the web-researcher working rules (stop and flag).
   - Record extraction date and source URL for each data point.

3. **Normalize and compile**
   - Convert all figures to annual USD (handle monthly, hourly, or foreign currency where needed).
   - Align levels across sources (e.g., Levels.fyi L5 = Glassdoor "Senior").
   - Compute percentile ranges: 25th, 50th, 75th for base, equity, and total comp.
   - Note sample sizes and data freshness; flag stale data (older than 12 months).

4. **Benchmark equity separately**
   - For equity, segment by company stage and funding round.
   - Include equity type (ISOs, RSUs, options), vesting schedule norms, and refresh policies if found.
   - Note the difference between pre-IPO equity (high variance) and public RSUs (lower variance).

5. **Generate comp research report**
   - Compile all findings into a structured report.
   - Include a recommended offer range with justification.
   - Flag where data is thin or conflicting across sources.

6. **Save to project**
   - Save the report to `projects/hiring/{slug}/research/comp-research.md`.
   - Create the research/ folder if it does not exist.
   - If no hiring project exists, save to a user-specified location.

## Output Standard

### Comp Research Report Format

```markdown
# Compensation Research -- {Role Title}, {Level}

**Market:** {location or remote}
**Company stage:** {seed | series-a | series-b | growth | public}
**Researched:** {YYYY-MM-DD}

---

## Summary

| Component | 25th %ile | 50th %ile | 75th %ile |
|---|---|---|---|
| Base salary | | | |
| Equity (annual) | | | |
| Bonus | | | |
| Total comp | | | |

## Recommended Offer Range

**Base:** ${low} -- ${high}
**Equity:** {range with type and vesting}
**Rationale:** {why this range, based on which sources}

## Source Data

### Levels.fyi
- URL: {url}
- Extracted: {date}
- Findings: {summary}

### Glassdoor
- URL: {url}
- Extracted: {date}
- Findings: {summary}

### Blind
- URL: {url}
- Extracted: {date}
- Findings: {summary}

### Pave
- Status: {extracted | paywalled | not available}
- Findings: {summary if available}

## Equity Benchmarks

{Equity details by company stage}

## Data Quality Notes

- {sample size caveats}
- {stale data warnings}
- {source conflicts}
```

## Working Rules

- Always cite the source and extraction date for every data point; never present scraped data as authoritative without provenance.
- If fewer than two sources return usable data, flag the research as low-confidence.
- Normalize titles carefully; a "Staff Engineer" at a 50-person startup differs from one at Google.
- Respect rate limits and login walls; do not bypass authentication on any comp site.
- Treat all scraped compensation data as approximate and note variance.
- If the role is uncommon or the market is thin, broaden the search to adjacent titles or geographies and note the substitution.
