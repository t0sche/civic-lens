# Arrow: ingestion-scraping

Tier 2 data collection via HTML scraping and RSS monitoring: eCode360, CivicPlus AgendaCenter, Bel Air legislation page, Harford County bills app.

## Status

**PARTIALLY_IMPLEMENTED** - 2026-03-19. ecode360.py, belair_legislation.py, and harford_bills.py are all implemented and running in CI. civicplus_agenda.py is deferred to Phase 8+. Test coverage exists only for harford_bills (test_harford_bills.py); test_ecode360.py, test_civicplus.py, and test_belair_legislation.py do not yet exist.

## References

### HLD
- docs/high-level-design.md §4.3 Tier 2 table, §5 D6 (eCode360 HTML over paid API)

### LLD
- docs/llds/ingestion-scraping.md (created 2026-03-14)

### EARS
- docs/specs/ingestion-scraping-specs.md (21 specs: 16 active, 5 deferred)

### Tests
- tests/ingestion/test_ecode360.py
- tests/ingestion/test_civicplus.py
- tests/ingestion/test_belair_legislation.py

### Code
- src/ingestion/scrapers/ecode360.py
- src/ingestion/scrapers/civicplus_agenda.py
- src/ingestion/scrapers/belair_legislation.py
- src/ingestion/scrapers/harford_bills.py

## Architecture

**Purpose:** Extract legislative data from government websites that lack APIs. All targets are stable CMS platforms (CivicPlus, eCode360, ASP.NET) with predictable HTML structures.

**Key Components:**
1. eCode360 scraper — hierarchical code extraction for county (HA0904) and town (BE2811) codes
2. CivicPlus AgendaCenter scraper — agenda/minute PDFs for 60+ county boards, 12 town boards
3. Bel Air legislation page scraper — ordinances/resolutions 2018+ from belairmd.org/213/Legislation
4. Harford County bills app scraper — council bills from apps.harfordcountymd.gov/Legislation/Bills
5. RSS monitor — CivicPlus RSS feeds for change detection at both jurisdictions

## EARS Coverage

See spec file in References above.

## Key Findings

- ecode360.py scrapes both BE2811 (Bel Air) and HA0904 (Harford County) hierarchically with configurable depth. Both run on the daily CI schedule.
- belair_legislation.py parses the belairmd.org/213/Legislation HTML table, maps status strings to the unified enum, and resolves PDF URLs.
- harford_bills.py scrapes the ASP.NET bills tracker at apps.harfordcountymd.gov with prefix-match status fallback.
- civicplus_agenda.py is a stub (Phase 8+) — correctly absent from CI and marked DEFERRED in specs.
- **MEDIUM**: test_ecode360.py, test_civicplus.py, and test_belair_legislation.py are listed in References but do not exist. Only test_harford_bills.py was created.

## Work Required

### Must Fix
1. eCode360 scraper for Bel Air town code (BE2811) — highest-value MVP source
2. Bel Air legislation page parser (simple HTML table → Bronze layer)
3. CivicPlus RSS feed poller for change detection
4. Scraper failure alerting (GitHub Actions notifications on non-zero exit)

### Should Fix
1. eCode360 scraper for Harford County code (HA0904)
2. CivicPlus AgendaCenter scraper (needs headless browser for JS year selection)
3. Harford County custom bills app scraper (reverse-engineer ASP.NET requests)

### Nice to Have
1. Incremental scraping (detect changes since last run, avoid re-scraping unchanged content)
2. robots.txt compliance checking
