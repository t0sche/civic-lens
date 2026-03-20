# Arrow: ingestion-federal

Federal API data collection: Congress.gov, GovInfo, USA Spending, OpenFEC, Census/ACS, FEMA NFHL, EPA ECHO, BLS LAUS, HUD FMR.

## Status

**MAPPED** - 2026-03-19. Sources researched and tiered. No ingestion clients built yet. Phase 9 sources are actionable; Phase 10+ are deferred.

## References

### HLD
- docs/high-level-design.md §4.3 Federal tier table

### LLD
- docs/llds/ingestion-federal.md (to be created in Phase 9)

### EARS
- docs/specs/ingestion-federal-specs.md (INGEST-FED-001 through INGEST-FED-060+)

### Tests
- tests/ingestion/test_congress.py — Phase 9
- tests/ingestion/test_usa_spending.py — Phase 9
- tests/ingestion/test_census.py — Phase 10

### Code
- src/ingestion/clients/congress.py — **NOT YET BUILT** (Phase 9)
- src/ingestion/clients/usa_spending.py — **NOT YET BUILT** (Phase 9)
- src/ingestion/clients/govinfo.py — **NOT YET BUILT** (Phase 9)
- src/ingestion/clients/census.py — **NOT YET BUILT** (Phase 10)
- src/ingestion/clients/fema_nfhl.py — **NOT YET BUILT** (Phase 10)
- src/ingestion/clients/epa_echo.py — **NOT YET BUILT** (Phase 10)
- src/ingestion/clients/bls_laus.py — **NOT YET BUILT** (Phase 10)
- src/ingestion/clients/hud_fmr.py — **NOT YET BUILT** (Phase 10)
- src/ingestion/clients/open_fec.py — **NOT YET BUILT** (Phase 10)

## Architecture

**Purpose:** Collect structured federal data into the Bronze layer. These are high-reliability free APIs that provide congressional, economic, environmental, and grant context uniquely relevant to Harford County residents.

**Key Design Context:**
- All Phase 9 sources use `api.data.gov` keys (single key works for Congress.gov, GovInfo, OpenFEC)
- USA Spending requires no auth — filter all queries by FIPS 24025 (Harford County)
- Aberdeen Proving Ground (APG) makes USA Spending data unusually relevant: large DoD contracts flow through Harford County
- ProPublica Congress API was **shut down February 4, 2025** — Congress.gov API is the replacement

**Key Components:**

### Phase 9 — High Value, Low Friction

1. **Congress.gov API** — Federal bills, amendments, members, committees, nominations. Covers 81st Congress onward. MD-01 (Rep. Andy Harris) covers Harford County.
   - Endpoint: `api.congress.gov`
   - Auth: Free `api.data.gov` key
   - Rate limit: 5,000 req/hr
   - Replaces: ProPublica Congress API (defunct Feb 4, 2025)

2. **GovInfo API** — Full text of bills, Federal Register, CFR, Congressional Record. Bulk download + document-level API.
   - Endpoint: `api.govinfo.gov`
   - Auth: Free `api.data.gov` key
   - Rate limit: Generous

3. **USA Spending API** — Federal contracts and grants filtered by Harford County FIPS 24025 or ZIP 21015.
   - Endpoint: `api.usaspending.gov`
   - Auth: None required
   - Rate limit: Generous

### Phase 10 — Contextual Data

4. **Census / ACS API** — Population, income, housing, poverty data for Harford County FIPS 24025. Key tables: B01003 (population ~265K), B19013 (median income), B25077 (median home value), B17001 (poverty).
   - Endpoint: `api.census.gov`
   - Auth: Free key

5. **FEMA NFHL** — National Flood Hazard Layer. Spatial queries by county. Returns flood zone (AE, A, X, VE), base flood elevations, floodway status. Harford County has full coverage.
   - Endpoint: `hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer`
   - Auth: None

6. **EPA ECHO** — Enforcement and compliance data for regulated facilities. Filter by county or ZIP. Inspection history, violations, penalties, pollutant data. Updated weekly.
   - Endpoint: `echo.epa.gov/tools/web-services/`
   - Auth: None

7. **BLS LAUS** — Local Area Unemployment Statistics. Harford County series: `LAUCN240250000000003`.
   - Endpoint: `api.bls.gov/publicAPI/v2/timeseries/data/`
   - Auth: Free key, 500 req/day

8. **HUD Fair Market Rents** — FMR by ZIP. 21015 in Baltimore-Columbia-Towson MSA. 2025 two-bedroom FMR: $1,965/month.
   - Endpoint: `huduser.gov/hudapi/public/fmr/data/`
   - Auth: Free token

9. **OpenFEC** — Official FEC contribution/expenditure data. MD-01 House, MD Senate races.
   - Endpoint: `api.open.fec.gov`
   - Auth: Free `api.data.gov` key, 1,000 req/hr

### Phase 11+ — Lower Priority

10. **OpenSecrets API** — Federal campaign finance, lobbying. Supplements OpenFEC with curated summaries.
11. **USDA NASS Quick Stats** — Agricultural data. Harford County: 1,831 farms.
12. **Census Geocoder** — Free address → lat/lon + census geography. Alternative to restricted USPS API.

## EARS Coverage

See docs/specs/ingestion-federal-specs.md

## Key Findings

- `api.data.gov` single key covers Congress.gov, GovInfo, OpenFEC — one key registration unlocks three high-value sources.
- Aberdeen Proving Ground context makes USA Spending unusually relevant vs. typical Maryland counties; DoD contract data directly affects local employment and land use.
- MGA Bulk CSV/JSON is listed under ingestion-apis, not here — it is a state (not federal) source.
- Regulations.gov POST API restricted since August 2025; GET endpoints still work.

## Work Required

### Phase 9 (Must Build)
1. `congress.py` — Fetch bills, members, votes for MD-01 and MD Senate from Congress.gov API
2. `usa_spending.py` — Fetch federal contracts/grants filtered to FIPS 24025
3. `govinfo.py` — Fetch full bill text and Federal Register notices (supplements Congress.gov metadata)
4. Register `api.data.gov` key and store in GitHub Actions secrets

### Phase 10 (Should Build)
1. `census.py` — Fetch ACS 5-year estimates for key tables at Harford County level
2. `fema_nfhl.py` — Spatial query for flood zone data by county boundary
3. `epa_echo.py` — Facility compliance and enforcement records by ZIP/county
4. `bls_laus.py` — Time-series unemployment data for Harford County
5. `hud_fmr.py` — Fair Market Rent and income limit data for ZIP 21015

### Phase 11+ (Nice to Have)
1. `open_fec.py` — Campaign finance contributions for MD-01 and MD Senate races
2. OpenSecrets integration for lobbying data
