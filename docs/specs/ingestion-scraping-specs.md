# Ingestion: Web Scraping Specifications

**Design Doc**: `/docs/llds/ingestion-scraping.md`
**Arrow**: `/docs/arrows/ingestion-scraping.md`

## eCode360 Scraper

- [ ] **INGEST-SCRAPE-001**: The system shall fetch the table of contents page for a given eCode360 municipality code and extract all chapter/part links with their titles and URLs.
- [ ] **INGEST-SCRAPE-002**: For each chapter, the system shall fetch the chapter page and extract individual sections by detecting section boundary elements (elements with section-related IDs, CSS classes, or heading elements).
- [ ] **INGEST-SCRAPE-003**: When no section-level elements are found within a chapter page, the system shall fall back to treating the entire chapter content area as a single section.
- [ ] **INGEST-SCRAPE-004**: The system shall preserve hierarchy metadata for each extracted section: chapter title, section title, hierarchy level, and municipality code.
- [ ] **INGEST-SCRAPE-005**: The system shall wait at least 1 second between HTTP requests to the eCode360 server.
- [ ] **INGEST-SCRAPE-006**: The system shall set the User-Agent header to a string identifying CivicLens with a contact URL on every request.
- [ ] **INGEST-SCRAPE-007**: The system shall write each extracted code section to bronze_documents with source set to "ecode360_belair" or "ecode360_harford" based on the municipality code.
- [ ] **INGEST-SCRAPE-008**: The system shall support scraping both Town of Bel Air (BE2811) and Harford County (HA0904) codes using the same scraper class with different municipality codes.

## Bel Air Legislation Page Scraper

- [ ] **INGEST-SCRAPE-010**: The system shall fetch the Bel Air legislation page at belairmd.org/213/Legislation and parse it for ordinance and resolution entries.
- [ ] **INGEST-SCRAPE-011**: For each legislation entry, the system shall extract: item identifier (number), title/description text, status label, item type (ordinance or resolution), and PDF link if present.
- [ ] **INGEST-SCRAPE-012**: The system shall classify entries as "ordinance" or "resolution" based on keyword presence in the entry text, skipping entries that match neither.
- [ ] **INGEST-SCRAPE-013**: The system shall map status labels from the page (Approved, Pending, Tabled, Expired, Rejected) to uppercase status strings, defaulting to "UNKNOWN" when no recognized label is found.
- [ ] **INGEST-SCRAPE-014**: When a PDF link is present, the system shall resolve relative URLs to absolute URLs using the belairmd.org base URL.
- [ ] **INGEST-SCRAPE-015**: The system shall write each legislation entry to bronze_documents as a JSON-serialized object with source set to "belair_legislation".

## Change Detection

- [ ] **INGEST-SCRAPE-020**: The system shall use the content_hash column in bronze_documents to detect changes between scraping runs — if the hash of newly scraped content matches the existing hash, the record is unchanged.
- [ ] **INGEST-SCRAPE-021**: The system shall track scraping runs in ingestion_runs with the same start/complete/fail pattern as API clients.

## CivicPlus RSS Feeds (Phase 9)

- [ ] **INGEST-SCRAPE-030**: The system shall poll CivicPlus RSS feeds at `belairmd.org/rss.aspx` using the URL pattern `RSSFeed.aspx?ModID={id}&CID={cat}` covering all 11 Bel Air board/commission feeds plus Alert Center, Calendar, News Flash, and Jobs.
- [ ] **INGEST-SCRAPE-031**: The system shall poll the Harford County RSS feed at `harfordcountymd.gov/RSS.aspx` for government news, DPW alerts, economic development, and emergency alerts.
- [ ] **INGEST-SCRAPE-032**: When new RSS entries are detected (by comparing GUIDs against bronze_documents source_ids), the system shall write the entry to bronze_documents with source set to `"civicplus_rss_belair"` or `"civicplus_rss_harford"`.
- [ ] **INGEST-SCRAPE-033**: The system shall store the RSS entry title, link, description, publication date, and originating board/committee in `raw_metadata`.
- [D] **INGEST-SCRAPE-034**: When an RSS entry links to an agenda or minutes PDF, the system shall fetch and store the PDF in bronze_documents for downstream extraction by the ingestion-pdf pipeline.
- [D] **INGEST-SCRAPE-035**: The system shall support historical agenda retrieval from AgendaCenter pages using a headless browser to interact with the JavaScript year selection dropdown.

## Harford County Bills Tracker (Phase 4)

- [x] **INGEST-SCRAPE-040**: The system shall scrape the Harford County custom bills application at apps.harfordcountymd.gov/Legislation/Bills, handling ASP.NET session state and ViewState.
- [x] **INGEST-SCRAPE-041**: For each county bill, the system shall extract: bill number, title, status, sponsors, and key dates.

## Harford County Zoning Board of Appeals (Phase 9)

- [ ] **INGEST-SCRAPE-045**: The system shall extend the existing harford_bills.py scraper to also retrieve ZBA cases from `hcgweb01.harfordcountymd.gov/Legislation/Zonings` using the same ASP.NET session pattern.
- [ ] **INGEST-SCRAPE-046**: For each ZBA case, the system shall extract: case number, applicant, property address, variance type, hearing date, and decision.
- [ ] **INGEST-SCRAPE-047**: ZBA cases shall be written to `bronze_documents` with `source` set to `"harford_zba"` and `source_id` set to the case number.

---

## Bel Air DocumentCenter (Phase 10) [DEFERRED]

- [D] **INGEST-SCRAPE-050**: The system shall crawl the Bel Air DocumentCenter at `belairmd.org/DocumentCenter/View/{ID}/` using sequential numeric IDs to discover and download documents.
- [D] **INGEST-SCRAPE-051**: The system shall categorize discovered documents by the 10 known categories: budgets (FY2012–2026), audits (2015–2024), capital plans, BOA minutes, Planning Commission minutes, Historic Preservation minutes, resolutions, and ordinances.
- [D] **INGEST-SCRAPE-052**: Each discovered document shall be written to `bronze_documents` with `source` set to `"belair_documentcenter"` and `source_id` set to the numeric document ID.
- [D] **INGEST-SCRAPE-053**: The system shall stop sequential crawling after encountering 50 consecutive 404 responses.

## MD Judiciary RSS (Phase 10) [DEFERRED]

- [D] **INGEST-SCRAPE-055**: The system shall poll the MD Courts RSS feed at `mdcourts.gov/rss.xml` for new appellate opinions, press releases, and judicial vacancies.
- [D] **INGEST-SCRAPE-056**: MD Judiciary RSS entries shall be written to `bronze_documents` with `source` set to `"md_judiciary_rss"`.
