# Arrow: ingestion-apis

Tier 1 data collection from structured APIs: Open States, LegiScan, MGA Bulk CSV, ArcGIS Hub, YouTube, MD Open Data Portal.

**Note:** Federal APIs (Congress.gov, Census, USA Spending, etc.) are tracked in the separate `ingestion-federal` arrow. This arrow covers state and local structured APIs only.

## Status

**IMPLEMENTED** - 2026-03-19. openstates.py and legiscan.py are both fully implemented with pagination, error handling, change_hash dedup, and Bronze layer writes. All 21 active INGEST-API specs verified implemented. legiscan.py is not yet scheduled in CI (workflow_dispatch only). arcgis.py and youtube.py are not yet built (NICE-TO-HAVE).

## References

### HLD
- docs/high-level-design.md §4.3 Tier 1 table, §5 D1 (Open States over MGA scraping)

### LLD
- docs/llds/ingestion-apis.md (created 2026-03-14)

### EARS
- docs/specs/ingestion-apis-specs.md (21 specs: 21 active, 0 deferred)

### Tests
- tests/ingestion/test_openstates.py
- tests/ingestion/test_legiscan.py

### Code
- src/ingestion/clients/openstates.py
- src/ingestion/clients/legiscan.py
- src/ingestion/clients/arcgis.py — **NOT YET BUILT** (NICE-TO-HAVE)
- src/ingestion/clients/youtube.py — **NOT YET BUILT** (NICE-TO-HAVE)

## Architecture

**Purpose:** Collect structured legislative and contextual data from third-party APIs into the Bronze layer. These are the highest-reliability, lowest-maintenance data sources.

**Key Components:**
1. Open States client — MD bills, votes, sponsors, committees via REST v3
2. LegiScan client — MD bills, full text, status history; fallback for Open States
3. ArcGIS Hub client — Harford County zoning, parcels, land use boundaries
4. YouTube Data API client — Bel Air meeting video metadata and auto-captions

## EARS Coverage

See spec file in References above.

## Key Findings

- openstates.py implements pagination, session/bill fetching, 5xx error handling, and Bronze upsert with change_hash dedup. Runs on the 6-hour CI schedule.
- legiscan.py implements getSessionList, getMasterList, getBill, ERROR/5xx handling, and change_hash dedup. Fully implemented but not yet scheduled in CI (workflow_dispatch only).
- **MEDIUM**: test_legiscan.py listed in References but does not exist — legiscan.py has no automated test coverage.
- **MEDIUM**: legiscan is commented out of the NORMALIZERS dict in normalize.py (TODO Phase 9) — Bronze data accumulates but Silver normalization does not run.
- arcgis.py and youtube.py are NICE-TO-HAVE items not yet built — removed from active Code references above.

## Work Required

### Must Fix
1. Open States API client with pagination, rate limiting, error handling
2. LegiScan API client (or bulk dataset downloader) for MD session data
3. Bronze layer write logic — raw API responses stored with source metadata
4. GitHub Actions workflow for scheduled API polling (every 6 hours for state bills)

### Should Fix
1. Deduplication between Open States and LegiScan data
2. MGA Bulk CSV/JSON ingestion — `mgaleg.maryland.gov/mgawebsite/Legislation/OpenData` — all bill metadata since 2013, no auth, updates throughout session
3. ArcGIS Hub client for Harford County GIS (zoning, parcels, land use)
4. Bel Air ArcGIS Hub client — `toba-data-hub-belairmd.hub.arcgis.com` — zoning, property boundaries, parks, infrastructure

### Nice to Have
1. YouTube auto-caption extraction for meeting searchability
2. MD Open Data Portal (SODA) client for 1,000+ demographic and contextual datasets
3. DLS RSS feeds — `dls.maryland.gov/feeds/` — lightweight alert for new legislative publications

## Deprecated Sources

| Source | Status | Replacement |
|--------|--------|-------------|
| **ProPublica Congress API** | **DEFUNCT** (GitHub archived Feb 4, 2025) | **Congress.gov API** in `ingestion-federal` arrow |
| **Google Civic Information — Representatives** | **DEFUNCT** (April 30, 2025) | Cicero API (commercial) or OCD-ID lookups |
