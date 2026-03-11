# Research Sources Reference

Common research sources and extraction patterns organized by research type.

## Company Research

### Company Website
- **URL pattern:** `https://{company-domain}/`
- **Key pages:** About, Team/Leadership, Product, Pricing, Blog, Careers
- **Extract:** Company description, founding date, team bios, product overview, pricing tiers, recent blog posts, open roles (indicator of growth areas)
- **Navigation:** Start at homepage, follow nav links to key sections
- **Tips:** Check footer for subsidiary info, legal entity names, office locations

### Crunchbase
- **URL pattern:** `https://www.crunchbase.com/organization/{company-slug}`
- **Key sections:** Summary, Financials, People, Technology, Signals
- **Extract:** Funding rounds (dates, amounts, investors), total raised, valuation (if available), employee count, founding date, categories, recent news
- **Login wall:** Free tier shows limited data. Flag for user if premium data needed.
- **Tips:** Check the "People" tab for key hires and departures

### LinkedIn Company Page
- **URL pattern:** `https://www.linkedin.com/company/{company-slug}/`
- **Key sections:** About, People, Posts, Jobs
- **Extract:** Company size range, headquarters, industry, specialties, employee growth signals, recent posts
- **Login wall:** LinkedIn requires login. Flag for user assistance.
- **Tips:** The "People" section shows employee distribution by function and location

### PitchBook
- **URL pattern:** `https://pitchbook.com/profiles/company/{id}`
- **Key sections:** Overview, Financials, Investors, Comparables
- **Extract:** Valuation, revenue estimates, deal history, investor list, comparable companies
- **Login wall:** Requires institutional subscription. Flag for user.
- **Tips:** Often the most detailed financial data for private companies

### Press Coverage
- **Discovery:** Use WebSearch for `"{company name}" funding OR launch OR partnership`
- **Sources:** TechCrunch, Bloomberg, Reuters, industry-specific publications
- **Extract:** Funding announcements, partnerships, product launches, executive quotes, growth metrics mentioned in press
- **Tips:** Search for last 12 months of coverage to get recent trajectory

### Product Hunt
- **URL pattern:** `https://www.producthunt.com/products/{product-slug}`
- **Extract:** Launch date, tagline, upvotes, maker comments, early user feedback
- **Tips:** Good for understanding initial positioning and market reception

### GitHub (if applicable)
- **URL pattern:** `https://github.com/{org}`
- **Extract:** Repository count, star counts, contributor activity, tech stack, open source strategy
- **Tips:** Check commit frequency, issue responsiveness, and contributor diversity

## Market Research

### Industry Reports (via search)
- **Discovery:** WebSearch for `{industry} market size {year}` or `{industry} industry report`
- **Sources:** Statista, Grand View Research, Markets and Markets, McKinsey, Bain
- **Extract:** Market size (TAM/SAM/SOM), growth rate (CAGR), key trends, major players
- **Paywall note:** Most full reports are paywalled. Extract summary data from previews and press releases about the reports.

### Analyst Coverage
- **Discovery:** WebSearch for `{company OR industry} analyst report OR equity research`
- **Extract:** Analyst ratings, price targets (public companies), growth estimates, competitive positioning
- **Tips:** Look for earnings call transcripts for public comps

### Competitive Landscape
- **Discovery:** WebSearch for `{company} competitors` or `{product category} comparison`
- **Sources:** G2, Capterra, Gartner, Forrester
- **Extract:** Competitor list, feature comparisons, user ratings, market positioning
- **Tips:** G2 and Capterra have structured comparison data

### Market Sizing Sources
- **Discovery:** WebSearch for `{market} TAM SAM SOM` or `{market} addressable market`
- **Sources:** Company S-1 filings (for public comps), industry associations, government statistics (BLS, Census)
- **Extract:** Total addressable market, serviceable market, growth projections, methodology

## Candidate Research

### LinkedIn Profile
- **URL pattern:** `https://www.linkedin.com/in/{profile-slug}/`
- **Key sections:** Experience, Education, Skills, Recommendations, Activity
- **Extract:** Work history (companies, titles, durations), education, skills, notable achievements, publication/speaking activity
- **Login wall:** Requires login. Flag for user assistance.
- **Tips:** Check activity feed for thought leadership signals

### GitHub Profile
- **URL pattern:** `https://github.com/{username}`
- **Extract:** Repository count, contribution graph, top languages, pinned projects, organization memberships
- **Tips:** Look at contribution consistency and project quality, not just star counts

### Portfolio / Personal Site
- **Discovery:** Often linked from LinkedIn or GitHub profile
- **Extract:** Projects, case studies, writing samples, design work, speaking engagements
- **Tips:** Check for a blog or writing section to assess communication skills

### Publications and Patents
- **Discovery:** WebSearch for `"{candidate name}" author OR patent OR publication`
- **Sources:** Google Scholar, USPTO, arXiv, Medium, Substack
- **Extract:** Publication titles, citations, patent filings, writing samples

## Regulatory and Filing Research

### SEC EDGAR
- **URL pattern:** `https://www.sec.gov/cgi-bin/browse-edgar?company={name}&CIK=&type=&dateb=&owner=include&count=40&search_text=&action=getcompany`
- **Key filings:** 10-K (annual), 10-Q (quarterly), S-1 (IPO), 8-K (material events), DEF 14A (proxy)
- **Extract:** Revenue, expenses, risk factors, executive compensation, shareholder info
- **Tips:** Use EDGAR full-text search for specific terms. S-1 filings are goldmines for market sizing data.

### State Business Filings
- **Discovery:** WebSearch for `{company name} {state} secretary of state business filing`
- **Sources:** State Secretary of State websites (varies by state)
- **Extract:** Entity type, formation date, registered agent, status (active/dissolved), officer names
- **Tips:** Delaware (most common for startups): `https://icis.corp.delaware.gov/ecorp/entitysearch/namesearch.aspx`

### Patent Search
- **URL pattern:** `https://patents.google.com/?q={company+name}&assignee={company}`
- **Extract:** Patent titles, filing dates, status, claims, technology areas
- **Tips:** Useful for assessing IP moat and R&D focus

### Court Records (PACER)
- **URL pattern:** `https://www.courtlistener.com/`
- **Extract:** Litigation history, case summaries, outcomes
- **Tips:** CourtListener is free; PACER charges per page. Use CourtListener first.

## Extraction Best Practices

1. **Structured data first**: Tables, lists, and key-value pairs are most reliable
2. **Date everything**: Always capture when data was extracted and when it was published
3. **Note confidence**: Flag whether data is confirmed (from official source) or estimated
4. **Capture context**: Include surrounding text for numbers and claims
5. **Link back**: Always store the source URL for verification
6. **Respect limits**: Do not aggressively scrape; use reasonable delays between requests
