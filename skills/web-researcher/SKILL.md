---
name: web-researcher
description: Research companies, markets, and candidates via Chrome automation and web search. Cross-type skill used by DD, hiring, and research projects for web scraping and structured data gathering.
---

# Web Researcher

Research companies, markets, candidates, and general topics using Claude in Chrome browser automation and web search. Gather structured data from public sources, save results to the project's `research/` folder, and index in the unified messages table as `type: "scrape"`.

## Trigger Phrases

- "Research CompanyX"
- "Look up market data on..."
- "Find info about candidate..."
- "Scrape the website for..."
- "Pull public data on..."
- "Do background research on..."

## Prerequisites

- Claude in Chrome extension must be connected
- The ingestion database must exist (`fund/metadata/db/ingestion.db` -- run `fund/metadata/init_db.py` if needed)
- A project workspace must exist for the target project (use `project-init` skill if needed)

## Core Workflow

1. **Determine research target and type**
   - Company research: corporate info, funding, team, product, financials
   - Market research: industry sizing, trends, competitive landscape, analyst reports
   - Candidate research: background, experience, portfolio, public contributions
   - General research: regulatory filings, press coverage, reference checks

2. **Plan research sources**
   - Identify which sources to hit based on target type (see `references/research-sources.md`)
   - Prioritize: company website first, then structured databases, then press/filings
   - Estimate scope and flag if research will be extensive

3. **For each source: navigate, extract, save**
   - Navigate to the source URL via Claude in Chrome
   - Use `read_page`, `get_page_text`, and `find` to extract key data
   - Handle login walls by stopping and flagging for user assistance
   - Handle CAPTCHAs by stopping and notifying the user
   - Save extracted content as markdown to the project's `research/` folder
   - Index in the unified messages table via `save_research.py`

4. **Normalize results to unified messages table**
   - Source: `web`
   - Type: `scrape`
   - source_id: URL hash or slugified URL
   - Dedup on `(source, source_id)` -- skip if already scraped
   - Store extraction metadata (source URL, extraction date, data sections found)

5. **Generate research summary**
   - After all sources are scraped, generate a `research/summary.md` file
   - Include key findings organized by category
   - Flag gaps where data was unavailable or sources were inaccessible
   - Include source URLs and extraction timestamps

## Browser Patterns

### Navigation and Extraction
- Use `navigate` to go to target URLs
- Use `read_page` to get the accessibility tree for structured data
- Use `get_page_text` to extract full text content from articles and pages
- Use `find` to locate specific elements (e.g., "revenue table", "founding team section")
- Use `WebSearch` for discovering source URLs before navigating

### Handling Obstacles
- **Login walls**: Stop extraction, log the URL as "requires_auth" in metadata, notify the user. Do not attempt to log in without explicit user direction.
- **CAPTCHAs**: Stop and notify the user. Do not attempt to solve CAPTCHAs.
- **Cookie banners**: Decline cookies (privacy-preserving default) and continue.
- **Paywalls**: Note the source as paywalled in metadata, extract whatever is visible, move on.
- **Rate limiting / blocking**: Back off, note the issue, try alternative sources.

### Data Extraction Priorities
For each page, extract in order of importance:
1. Structured data (tables, lists, key-value pairs)
2. Key narrative sections (about, overview, description)
3. Dates and timestamps
4. Links to related resources

## Output Standard

### Folder Structure

```
{project_root}/research/
  {source-slug}.md          # Individual source extractions
  summary.md                # Generated research summary
```

Example for a company DD project:
```
fund/projects/acme-corp/research/
  acme-corp-website.md
  acme-corp-crunchbase.md
  acme-corp-linkedin.md
  acme-corp-press-techcrunch.md
  summary.md
```

### Individual Source File Format

```markdown
# {Source Name} -- {Target Name}

**Source URL:** {url}
**Extracted:** {YYYY-MM-DD HH:MM}
**Status:** complete | partial | requires_auth | paywalled

---

## Key Data

{Extracted content organized by section}

## Raw Notes

{Any additional context or caveats about the extraction}
```

## Scripts

- `scripts/save_research.py` -- Save research results and index in the database
  - `save_research_item(conn, project_slug, project_type, source_url, title, content, metadata)` -- Save a single research item
  - `get_research_status(project_slug)` -- Check what has been researched for a project

## Error Handling

- If a source is unreachable, log the error and continue with the next source
- If the database is locked, retry up to 3 times with 2-second backoff
- If Chrome extension is disconnected, stop and notify the user
- If extraction yields no useful content, mark the source as "empty" and move on

## Working Rules

- Always save raw extracted content before summarizing -- never discard source data
- Respect robots.txt and rate limits; do not aggressively scrape
- Never attempt to bypass authentication or CAPTCHAs
- Use web search to discover URLs; use Chrome automation to extract content
- Tag all messages table entries with the project slug in project_tags
- Copyright: extract factual data and metadata, not full copyrighted articles
