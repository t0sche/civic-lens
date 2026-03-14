# Arrow: ingestion-apis

Tier 1 data collection from structured APIs: Open States, LegiScan, ArcGIS Hub, YouTube, MD Open Data Portal.

## Status

**MAPPED** - 2026-03-14. Data audit complete; API endpoints identified; clients not yet built.

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
- src/ingestion/clients/arcgis.py
- src/ingestion/clients/youtube.py

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

None yet — UNMAPPED.

## Work Required

### Must Fix
1. Open States API client with pagination, rate limiting, error handling
2. LegiScan API client (or bulk dataset downloader) for MD session data
3. Bronze layer write logic — raw API responses stored with source metadata
4. GitHub Actions workflow for scheduled API polling (every 6 hours for state bills)

### Should Fix
1. Deduplication between Open States and LegiScan data
2. ArcGIS Hub client for zoning/parcel data (useful for chat context)

### Nice to Have
1. YouTube auto-caption extraction for meeting searchability
2. MD Open Data Portal (SODA) client for demographic context datasets
