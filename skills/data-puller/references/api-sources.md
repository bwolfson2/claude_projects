# Common API Sources for Data Pulls

Reference list of public APIs and data sources commonly used during due diligence.

## SEC EDGAR API

- **Base URL:** `https://efts.sec.gov/LATEST/`
- **Full-text search:** `https://efts.sec.gov/LATEST/search-index?q={query}&dateRange=custom&startdt={start}&enddt={end}`
- **Company filings:** `https://data.sec.gov/submissions/CIK{cik_padded}.json`
- **Filing documents:** `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/`
- **Rate limit:** 10 requests/second, must include `User-Agent` header with contact email
- **Common filing types:** 10-K (annual), 10-Q (quarterly), 8-K (current events), S-1 (IPO), DEF 14A (proxy)
- **Notes:** No API key required. CIK numbers are zero-padded to 10 digits.

## OpenCorporates

- **Base URL:** `https://api.opencorporates.com/v0.4/`
- **Company search:** `https://api.opencorporates.com/v0.4/companies/search?q={name}`
- **Company details:** `https://api.opencorporates.com/v0.4/companies/{jurisdiction_code}/{company_number}`
- **Officers search:** `https://api.opencorporates.com/v0.4/officers/search?q={name}`
- **Rate limit:** 500 requests/month (free tier), higher with API key
- **API key:** Optional for basic lookups, required for bulk access
- **Notes:** Good for corporate registration data, officer lists, jurisdiction info.

## Crunchbase API

- **Base URL:** `https://api.crunchbase.com/api/v4/`
- **Organization search:** `https://api.crunchbase.com/api/v4/autocompletes?query={name}`
- **Organization details:** `https://api.crunchbase.com/api/v4/entities/organizations/{permalink}`
- **Funding rounds:** included in organization details with `field_ids` parameter
- **API key:** Required (paid plans only for most endpoints)
- **Rate limit:** Varies by plan
- **Notes:** Best source for startup funding history, investors, and key people. Free tier is very limited.

## PitchBook (No Public API)

- **Access:** Requires institutional subscription
- **Fallback:** Use Chrome scrape if the user has an active session
- **Data available:** Company profiles, funding rounds, valuations, investors, comparable transactions
- **Notes:** No public API. Data must be scraped from the web UI or exported manually.

## Public Datasets and Government APIs

### Companies House (UK)

- **Base URL:** `https://api.company-information.service.gov.uk/`
- **Company search:** `/search/companies?q={name}`
- **Company profile:** `/company/{company_number}`
- **Filing history:** `/company/{company_number}/filing-history`
- **API key:** Required (free registration)

### US Census Bureau

- **Base URL:** `https://api.census.gov/data/`
- **Economic data:** `https://api.census.gov/data/{year}/cbp?get=ESTAB,EMP&for=us:*&NAICS2017={code}`
- **API key:** Required (free registration)
- **Notes:** Useful for market sizing by industry (NAICS codes).

### Federal Reserve Economic Data (FRED)

- **Base URL:** `https://api.stlouisfed.org/fred/`
- **Series data:** `https://api.stlouisfed.org/fred/series/observations?series_id={id}&api_key={key}&file_type=json`
- **API key:** Required (free registration)
- **Notes:** Macro-economic data, interest rates, GDP, unemployment, etc.

### World Bank Open Data

- **Base URL:** `https://api.worldbank.org/v2/`
- **Country indicators:** `https://api.worldbank.org/v2/country/{code}/indicator/{indicator}?format=json`
- **No API key required**
- **Notes:** International economic indicators, development data.

### USAspending.gov

- **Base URL:** `https://api.usaspending.gov/api/v2/`
- **Award search:** `/search/spending_by_award/`
- **Recipient lookup:** `/recipient/duns/{duns_number}/`
- **No API key required**
- **Notes:** Federal contracts and grants data. Useful for government contractor diligence.

## General Web Sources (Chrome Scrape)

These sources lack public APIs and require Chrome-based scraping:

- **LinkedIn** -- Company profiles, employee counts, growth signals (requires login)
- **Glassdoor** -- Employee reviews, salary data, company ratings
- **G2/Capterra** -- Software product reviews and comparisons
- **SimilarWeb** -- Website traffic estimates (limited free data)
- **App Annie / data.ai** -- Mobile app download estimates

## Request Headers Template

For API calls, always include proper headers:

```
User-Agent: VFT-DueDiligence/1.0 (contact@vft.institute)
Accept: application/json
```

For SEC EDGAR specifically, the `User-Agent` header is mandatory and must include a contact email.
