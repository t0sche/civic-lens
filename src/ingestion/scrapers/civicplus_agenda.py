"""
CivicPlus AgendaCenter scraper — stub for Phase 4.

Scrapes meeting agendas and minutes from CivicPlus-powered sites.
Uses identical CivicPlus AgendaCenter modules, so one scraper
serves multiple jurisdictions with different base URLs configured
in civic-lens.config.json.

NOTE: AgendaCenter uses JavaScript for year selection dropdown,
requiring a headless browser (Playwright) for full historical access.
RSS feeds provide change detection without JS rendering.

@spec INGEST-SCRAPE-030, INGEST-SCRAPE-031, INGEST-SCRAPE-032
"""

# TODO: Implement in Phase 9+ (post-County Expansion)
# - RSS feed polling for change detection (low effort)
# - Headless browser scraping for historical agendas (higher effort)
# - PDF download and handoff to extractors/pdf_extractor.py
