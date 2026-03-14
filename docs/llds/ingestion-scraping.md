# Ingestion: Web Scraping

**Created**: 2026-03-14
**Status**: Design Phase
**HLD Reference**: §4.3 Tier 2, §5 D6 (eCode360 HTML over paid API)

## Context and Design Philosophy

Tier 2 sources are government websites without APIs. The data is publicly available but locked in HTML pages and PDF downloads served by CMS platforms (CivicPlus, eCode360) and custom applications (Harford County bills tracker).

The design philosophy is **defensive scraping**: identify the most stable structural elements to parse against, include polite delays between requests, set an honest User-Agent, and build change-detection so we know immediately when a scraper breaks rather than silently returning stale data.

All scrapers share a common pattern: fetch HTML → parse with BeautifulSoup → extract structured data → write to Bronze layer. CivicPlus RSS feeds provide a lightweight change-detection layer on top.

## eCode360 Scraper

### Target Sites

Two municipalities use General Code's eCode360 platform:
- **Town of Bel Air**: `ecode360.com/BE2811` — Charter + 7 admin chapters + general legislation
- **Harford County**: `ecode360.com/HA0904` — Full county code

eCode360 serves well-structured HTML with hierarchical navigation. Each municipality has a table of contents page linking to chapters, and each chapter page contains sections rendered as structured HTML elements.

### Scraping Strategy

The scraper operates in two passes:

**Pass 1 — Table of Contents**: Fetch the municipality's root page (`ecode360.com/{CODE}`), parse all chapter/part links from the TOC navigation. Each link yields a `CodeEntry` with title, URL, and level.

**Pass 2 — Chapter Content**: For each chapter, fetch the full chapter page and extract individual sections. eCode360 renders sections in `div` elements with identifiable classes and IDs. Section boundaries are detected by heading elements (`h2`, `h3`, `h4`) or section-specific CSS classes.

**HTML structure patterns observed on eCode360:**
- Chapter pages have a content area with sequentially numbered sections
- Section headings typically follow the pattern `§{chapter}-{number}` (e.g., `§165-23`)
- Subsections are nested within parent section containers
- Cross-references use internal anchor links (`#sec-{id}`)
- The page structure is server-rendered HTML with minimal JavaScript

### Section Boundary Detection

Legal code has natural section boundaries that must be preserved for meaningful chunking downstream. The scraper identifies boundaries using a priority cascade:

1. Elements with `id` attributes starting with `sec` or containing section numbers
2. Elements with class names containing `Section` or `section-content`
3. Heading elements (`h2`–`h4`) followed by content blocks
4. Paragraph-level fallback: if no section elements are found, the entire chapter content is treated as a single section

This cascade handles the variation in eCode360's rendering across municipalities — not all codes use the same HTML structure.

### Hierarchy Preservation

Each Bronze document includes metadata that preserves the hierarchy:
- `chapter`: The parent chapter title (e.g., "Chapter 165 - Development Regulations")
- `section_title`: The section heading (e.g., "§165-23 Fences and walls")
- `level`: "chapter", "article", or "section"
- `municipality_code`: "BE2811" or "HA0904"

This metadata flows through to the Silver layer's `section_path` field and ultimately into the Gold layer's chunk metadata, enabling the RAG system to display breadcrumbs like "Town of Bel Air Code > Chapter 165 > §165-23" in citations.

### Polite Crawling

- **Request delay**: 1 second between page fetches (configurable via `REQUEST_DELAY`)
- **User-Agent**: `CivicLens/0.1 (civic transparency project; contact: github.com/...)` — honest identification with contact info
- **robots.txt**: The scraper should check robots.txt before first run (eCode360 generally permits crawling)
- **Session reuse**: A single `requests.Session` for connection pooling and cookie persistence

### Change Detection

eCode360 doesn't provide RSS or update feeds. Change detection relies on the Bronze layer's `content_hash`:

1. Scrape a section → compute SHA-256 of extracted text
2. Upsert to Bronze with the hash
3. If hash matches existing row → no change, skip normalization
4. If hash differs → content changed, trigger re-normalization and re-embedding

Full re-scrapes run daily. The content hash makes this efficient — only genuinely changed sections trigger downstream processing.

## Bel Air Legislation Page Scraper

### Target

`belairmd.org/213/Legislation` — a single CivicPlus page listing ordinances and resolutions from 2018 onward with status labels and PDF links.

### Page Structure

This is the simplest scraping target. The page is a CivicPlus content area with a structured listing of legislative items. Each entry contains:
- Item identifier (ordinance/resolution number)
- Title or description text
- Status label (Approved, Pending, Tabled, Expired, Rejected)
- Link to the full document PDF in the CivicPlus DocumentCenter

The scraper parses the content area, classifies each entry as an ordinance or resolution based on keyword matching, extracts the status, and captures any PDF links.

### Output to Bronze

Each legislation entry is serialized as JSON and written to Bronze with:
- `source`: `"belair_legislation"`
- `source_id`: The item identifier (e.g., "Ordinance 743")
- `document_type`: `"ordinance"` or `"resolution"`
- `raw_content`: JSON with number, title, status, item_type, pdf_url
- `raw_metadata`: Structured fields for status and has_pdf flag

## CivicPlus AgendaCenter Scraper (Phase 4)

### Shared Platform

Both Harford County and Bel Air use CivicPlus CivicEngage with the AgendaCenter module. A single scraper class can serve both sites with different base URLs:
- County: `harfordcountymd.gov/AgendaCenter`
- Town: `belairmd.org/AgendaCenter`

### RSS-First Strategy

CivicPlus provides RSS feeds at `/rss.aspx` that cover agenda updates, calendar events, and news. The recommended approach is RSS polling first, full scraping second:

1. Poll RSS feeds every 6 hours for new agenda/minute entries
2. For new entries, fetch the linked PDF from the AgendaCenter
3. Full scrape (historical backfill) only on initial setup or recovery

### JavaScript Challenge

The AgendaCenter uses JavaScript for the year selection dropdown. Fetching agendas for years other than the current one requires either:
- **Option A**: Playwright/headless browser to interact with the dropdown — more reliable but heavier dependency
- **Option B**: Reverse-engineer the AJAX request the dropdown triggers — lighter but more brittle

For Phase 4, Option A is recommended since Playwright is well-supported in GitHub Actions.

## Harford County Bills Tracker (Phase 4)

### Target

`apps.harfordcountymd.gov/Legislation/Bills` — a custom ASP.NET web application (not Legistar).

This is the most challenging scraping target because it's a bespoke application. The approach requires:
1. Session initialization (GET the page, capture cookies and ViewState)
2. Form POST with appropriate parameters to search/list bills
3. Parse the response HTML for bill metadata

The fragility of this scraper is the primary risk in the county data pipeline. The mitigation is monitoring: if the scraper returns zero results or encounters unexpected HTML structure, it fails loudly via `ingestion_runs`.

## Shared Scraper Infrastructure

### Base Scraper Class

All scrapers share common behaviors that should be extracted into a base class:
- Request session with User-Agent and connection pooling
- Configurable request delay
- Bronze layer writing via `upsert_bronze_document`
- Ingestion run tracking (start/complete)
- Error logging and run failure recording

### Failure Modes and Recovery

Scrapers fail in predictable ways. The recovery strategy for each:

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Site down (HTTP 5xx) | Request exception | Retry 2x with backoff, then fail run |
| Structure changed (parse error) | Zero results or exception in parsing | Fail run, alert. Manual inspection needed. |
| Rate limited (HTTP 429) | Response status | Increase REQUEST_DELAY, retry |
| Content unchanged | All content_hash matches | No-op (expected success case) |
| Partial failure (some pages fail) | Per-page error count | Complete what we can, log failures, partial success |

## Open Questions & Future Decisions

### Resolved
1. ✅ eCode360 HTML scraping over paid API ($845/year) — HTML is stable enough; paid API is an optimization
2. ✅ RSS-first for CivicPlus change detection — low effort, high reliability
3. ✅ 1-second request delay — sufficient for polite crawling without excessive runtime

### Deferred
1. Playwright dependency for AgendaCenter historical access — add in Phase 4
2. Whether to scrape Harford County bills tracker or build a relationship with county IT for data access — explore both in Phase 4
3. robots.txt compliance checker — manual check is fine for 3 sites; automate if generalizing
4. eCode360 paid API — revisit if scraper maintenance becomes a burden or the project gets funding

## References

- eCode360 platform: https://ecode360.com
- CivicPlus CivicEngage: https://www.civicplus.com/civicengage
- BeautifulSoup docs: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
