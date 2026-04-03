# Ingestion: Federal API Clients Specifications

**Arrow**: `/docs/arrows/ingestion-federal.md`

**Note on ProPublica:** The ProPublica Congress API was shut down February 4, 2025 (GitHub archived). All federal legislative data now comes from the Congress.gov API (`api.congress.gov`). Any references to ProPublica in earlier code or docs are obsolete.

**Note on api.data.gov:** A single `api.data.gov` key covers Congress.gov, GovInfo, and OpenFEC. Register once at `api.data.gov` and store as `DATA_GOV_API_KEY` in secrets.

---

## Phase 9 — Congress.gov Client

- [ ] **INGEST-FED-001**: The system shall fetch Maryland-related federal bills from Congress.gov using the `/v3/bill` endpoint filtered by subject or sponsor state.
- [ ] **INGEST-FED-002**: The system shall fetch committee assignments and voting records for MD-01 House seat (currently Andy Harris) and both Maryland Senate seats from Congress.gov.
- [ ] **INGEST-FED-003**: The system shall paginate Congress.gov results using the `offset` parameter until all pages are consumed, respecting the 5,000 req/hr rate limit.
- [ ] **INGEST-FED-004**: The system shall store the `api.data.gov` key in the `DATA_GOV_API_KEY` environment variable and pass it as the `api_key` query parameter on every request.
- [ ] **INGEST-FED-005**: If Congress.gov returns HTTP 429, the system shall retry with exponential backoff starting at 10 seconds, up to 3 retries.
- [ ] **INGEST-FED-006**: The system shall write each bill record to `bronze_documents` with `source` set to `"congress_gov"` and `source_id` set to the bill's congress + type + number (e.g., `"118-HR-1234"`).
- [ ] **INGEST-FED-007**: The system shall use the `content_hash` column to skip bills whose content has not changed since the last ingestion run.

## Phase 9 — GovInfo Client

- [ ] **INGEST-FED-010**: The system shall fetch federal bill full text from GovInfo using the `/v0/packages` endpoint filtered to `BILLS` collection and Maryland sponsor.
- [ ] **INGEST-FED-011**: The system shall store GovInfo package content in `bronze_documents` with `source` set to `"govinfo"` and link back to the corresponding `congress_gov` bill via `raw_metadata.congress_gov_id`.
- [ ] **INGEST-FED-012**: The system shall fetch Federal Register notices relevant to Harford County or Maryland using the GovInfo `/v0/published` endpoint filtered by agency and date range.

## Phase 9 — USA Spending Client

- [ ] **INGEST-FED-020**: The system shall query the USA Spending `/api/v2/search/spending_by_award/` endpoint filtering by recipient county FIPS code `24025` (Harford County, MD).
- [ ] **INGEST-FED-021**: The system shall also query by ZIP code `21015` as a secondary filter to capture spending targeted specifically at Bel Air.
- [ ] **INGEST-FED-022**: For each award record, the system shall extract: award ID, recipient name, awarding agency, funding amount, period of performance, award type, and description.
- [ ] **INGEST-FED-023**: The system shall write each award to `bronze_documents` with `source` set to `"usa_spending"` and note Aberdeen Proving Ground (APG) contractor awards in `raw_metadata.is_apg_related` based on keyword matching.
- [ ] **INGEST-FED-024**: The system shall paginate USA Spending results using the `page` parameter and `has_next` field until all results are retrieved.

## Phase 9 — Ingestion Run Tracking (Federal)

- [ ] **INGEST-FED-030**: Each federal client shall record an `ingestion_runs` row with `source` set to the client name (`congress_gov`, `govinfo`, `usa_spending`) using the same start/complete/fail pattern as existing API clients.
- [ ] **INGEST-FED-031**: When a federal ingestion run fails, the system shall log the HTTP status code, response body (truncated to 500 chars), and endpoint URL in the `error_message` column.

---

## Phase 10 — Census / ACS Client [DEFERRED]

- [D] **INGEST-FED-040**: The system shall fetch ACS 5-year estimates for Harford County (FIPS 24025) from Census API table B01003 (total population).
- [D] **INGEST-FED-041**: The system shall fetch ACS 5-year estimates for Harford County from Census API table B19013 (median household income).
- [D] **INGEST-FED-042**: The system shall fetch ACS 5-year estimates for Harford County from Census API table B25077 (median home value).
- [D] **INGEST-FED-043**: The system shall fetch ACS 5-year estimates for Harford County from Census API table B17001 (poverty rate).
- [D] **INGEST-FED-044**: Census data shall be stored in `bronze_documents` with `source` set to `"census_acs"` and `source_id` set to `"{table}_{year}_{fips}"`.

## Phase 10 — FEMA NFHL Client [DEFERRED]

- [D] **INGEST-FED-050**: The system shall query the FEMA National Flood Hazard Layer ArcGIS REST endpoint for flood zone polygons within Harford County boundaries.
- [D] **INGEST-FED-051**: For each flood zone record, the system shall extract: zone designation (AE, A, X, VE), base flood elevation, floodway status, effective date, and geometry.
- [D] **INGEST-FED-052**: FEMA NFHL data shall be stored with `source` set to `"fema_nfhl"` and refreshed no more than weekly (data updates are infrequent).

## Phase 10 — EPA ECHO Client [DEFERRED]

- [D] **INGEST-FED-055**: The system shall query the EPA ECHO web services for regulated facilities in Harford County filtered by county code.
- [D] **INGEST-FED-056**: For each facility, the system shall fetch inspection history, violations, enforcement actions, and pollutant discharge data.
- [D] **INGEST-FED-057**: EPA ECHO data shall be stored with `source` set to `"epa_echo"` and refreshed weekly (data updates weekly).

## Phase 10 — BLS LAUS Client [DEFERRED]

- [D] **INGEST-FED-060**: The system shall fetch the Harford County Local Area Unemployment Statistics time series from BLS API v2 using series ID `LAUCN240250000000003`.
- [D] **INGEST-FED-061**: The system shall store the most recent 24 months of monthly unemployment rate, labor force, employment, and unemployment count data.
- [D] **INGEST-FED-062**: BLS LAUS data shall be stored with `source` set to `"bls_laus"` and refreshed monthly.

## Phase 10 — HUD Fair Market Rents Client [DEFERRED]

- [D] **INGEST-FED-065**: The system shall fetch Fair Market Rent data for ZIP code 21015 from the HUD API (`huduser.gov/hudapi/public/fmr/data/`).
- [D] **INGEST-FED-066**: The system shall also fetch income limits for the Baltimore-Columbia-Towson MSA (which includes Harford County).
- [D] **INGEST-FED-067**: HUD FMR data shall be stored with `source` set to `"hud_fmr"` and refreshed annually (FMR updates each October).

## Phase 10 — OpenFEC Client [DEFERRED]

- [D] **INGEST-FED-070**: The system shall fetch campaign finance filings for Maryland Congressional District 1 (MD-01) candidates from the OpenFEC API.
- [D] **INGEST-FED-071**: The system shall fetch candidate and committee data for both Maryland Senate seats.
- [D] **INGEST-FED-072**: OpenFEC data shall be stored with `source` set to `"open_fec"`.
