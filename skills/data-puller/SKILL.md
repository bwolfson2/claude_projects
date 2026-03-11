---
name: data-puller
description: Fetch structured data from APIs, web tables, and public sources. Normalize to JSON/CSV and save to the project data/ folder with ingestion database indexing. Use when you need to pull data from SEC EDGAR, OpenCorporates, government APIs, or scrape HTML tables.
---

# VFT Data Puller

Fetch structured data from APIs, web tables, CSV/JSON endpoints, and public filings. Normalize the output to a standard format (JSON or CSV), save to the project's `data/` folder, and index in the unified messages table.

## Trigger Phrases

- "Pull data from..."
- "Fetch SEC filing..."
- "Get market data..."
- "Extract table from..."

## Prerequisites

- The ingestion database must exist (`fund/metadata/db/ingestion.db` -- run `fund/metadata/init_db.py` if needed)
- For web scraping: Claude in Chrome extension must be connected
- For API calls: network access to the target endpoint

## Core Workflow

1. **Identify data source** -- Determine the type of source: API endpoint, web table, CSV/JSON URL, or SEC/government filing
2. **Fetch data** -- Use the fallback chain: API call first, then Chrome scrape if API unavailable
3. **Parse and normalize** -- Convert raw response to structured format (JSON or CSV)
4. **Save to project** -- Write the normalized data to `{project_root}/data/{source-slug}.{json|csv}`
5. **Index in database** -- Insert a row in the unified `messages` table with `source="web"` and `type="document"` or `type="scrape"`

## Fallback Chain

The skill uses a tiered approach to data retrieval:

1. **API first** -- If a public API exists for the source (e.g., SEC EDGAR, OpenCorporates), call it directly via HTTP
2. **Chrome scrape** -- If no API is available or the API fails, use Claude in Chrome to navigate to the page, extract the data from HTML tables or structured elements
3. **Flag for user** -- If both API and Chrome scrape fail, log the failure and notify the user with the source URL and error details

## Supported Formats

| Format | Input | Output |
|--------|-------|--------|
| JSON | API responses, `.json` URLs | `.json` files |
| CSV | Tabular data, `.csv` URLs | `.csv` files |
| Excel | `.xlsx` downloads | Converted to `.csv` |
| HTML tables | Web page tables via Chrome | Extracted to `.json` or `.csv` |

## Data Folder Structure

```
{project_root}/data/
  sec-10k-2025.json
  opencorporates-company-profile.json
  market-data-q4-2025.csv
  scraped-financials-table.csv
```

## Slug Generation

Source URL or name --> slug rules:
- Lowercase, strip non-alphanumeric chars except hyphens
- Collapse multiple hyphens
- Truncate to 60 chars
- If duplicate slug exists in the same data folder, append `-2`, `-3`, etc.

## Database Indexing

When inserting into the `messages` table:
- `source`: `"web"`
- `source_id`: SHA-256 hash of `source_url + timestamp` for dedup
- `type`: `"document"` for API-fetched data, `"scrape"` for Chrome-scraped data
- `subject`: Descriptive name of the data pull (e.g., "SEC 10-K filing for Acme Corp")
- `body`: JSON summary of the data (first 500 chars or row count + column names)
- `raw_path`: Absolute path to the saved data file
- `metadata`: JSON with `source_url`, `format`, `row_count`, `columns`, `pull_timestamp`

## Scripts

- `scripts/pull_data.py` -- Helper for saving data and indexing
  - `save_data_pull(conn, project_slug, project_type, source_url, data, format, metadata)` -- Save data file and insert messages row
  - `extract_html_table(html_content)` -- Parse HTML tables into list-of-dicts
  - `get_pull_status()` -- Show recent data pulls from the database

## Chrome Scraping Patterns

### Extracting HTML Tables
- Navigate to the target URL via Claude in Chrome
- Use `get_page_text` or `read_page` to get the page content
- Identify `<table>` elements and extract rows/columns
- Normalize header names (lowercase, underscores for spaces)

### Handling Pagination
- Check for "Next" or pagination controls
- Iterate through pages, collecting all rows
- Merge results into a single dataset

### Dynamic Content
- Wait for JavaScript-rendered content to load
- Use `read_page` to verify data is present before extraction
- Retry with increasing delays if content is still loading

## Error Handling

- If an API returns a non-200 status, log the error and fall back to Chrome scrape
- If Chrome scrape fails to find expected table structure, flag for user with the URL
- If the database is locked, retry up to 3 times with 2-second backoff
- If saving a file fails due to filesystem issues, log and report to user
- Rate limit API calls: respect `Retry-After` headers and add 1-second delays between requests
