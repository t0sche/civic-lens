# Ingestion: API Clients Specifications

**Design Doc**: `/docs/llds/ingestion-apis.md`
**Arrow**: `/docs/arrows/ingestion-apis.md`

## Open States Client

- [ ] **INGEST-API-001**: The system shall fetch Maryland state bills from the Open States v3 REST API using the jurisdiction ID `ocd-jurisdiction/country:us/state:md/government`.
- [ ] **INGEST-API-002**: When fetching bills, the system shall request the `abstracts,actions,sponsorships,sources` includes to retrieve full bill metadata in a single request.
- [ ] **INGEST-API-003**: The system shall paginate through all result pages by incrementing the `page` parameter until `page >= pagination.max_page`.
- [ ] **INGEST-API-004**: When the `updated_since` parameter is provided, the system shall fetch only bills updated after that date to support incremental ingestion.
- [ ] **INGEST-API-005**: The system shall send the API key in the `X-API-KEY` request header on every request.
- [ ] **INGEST-API-006**: If the API returns HTTP 429 (rate limited), then the system shall retry with exponential backoff starting at 5 seconds, up to 3 retries.
- [ ] **INGEST-API-007**: If the API returns HTTP 5xx, then the system shall retry once after 10 seconds, then fail the ingestion run.
- [ ] **INGEST-API-008**: If the API returns HTTP 4xx (excluding 429), then the system shall fail immediately without retry.

## LegiScan Client

- [ ] **INGEST-API-010**: The system shall fetch the list of available Maryland legislative sessions from LegiScan via the `getSessionList` operation.
- [ ] **INGEST-API-011**: When no session ID is provided, the system shall use the most recent session from the session list.
- [ ] **INGEST-API-012**: The system shall fetch the master bill list for a session via the `getMasterList` operation, then fetch full detail for each bill via the `getBill` operation.
- [ ] **INGEST-API-013**: If the LegiScan API returns a status of "ERROR", then the system shall raise an exception with the alert message from the response.

## Bronze Layer Writing

- [ ] **INGEST-API-020**: The system shall write each fetched bill as a JSON-serialized document to the `bronze_documents` table with source set to the API name ("openstates" or "legiscan").
- [ ] **INGEST-API-021**: The system shall compute a SHA-256 hash of the raw_content and store it in the content_hash column for change detection.
- [ ] **INGEST-API-022**: When a document with the same (source, source_id) already exists, the system shall upsert the record, updating raw_content, raw_metadata, url, fetched_at, and content_hash.
- [ ] **INGEST-API-023**: The system shall store the bill identifier, session, and classification in the raw_metadata JSONB column as convenience fields.

## Ingestion Run Tracking

- [ ] **INGEST-API-030**: When an ingestion run starts, the system shall insert a row into ingestion_runs with status "running" and return the run ID.
- [ ] **INGEST-API-031**: When an ingestion run completes successfully, the system shall update the run row with status "success", completed_at timestamp, and record counts (fetched, new, updated).
- [ ] **INGEST-API-032**: If an ingestion run fails with an exception, then the system shall update the run row with status "failed", completed_at timestamp, and the error message.

## Data Validation

- [ ] **INGEST-API-040**: The system shall reject and skip any record where raw_content is empty or whitespace-only, logging a warning.
- [ ] **INGEST-API-041**: The system shall reject and skip any record where source_id is empty or null, logging a warning.

---

## MGA Bulk CSV/JSON Client [Phase 9]

**Note:** The MGA Open Data endpoint (`mgaleg.maryland.gov/mgawebsite/Legislation/OpenData`) provides all Maryland General Assembly bill metadata since 2013 — number, sponsor, synopsis, status, progress, hearing dates, committees, passage, and 79 subject categories. No API key required. This supplements Open States/LegiScan with direct-from-source data and 79-category subject tagging unavailable in third-party APIs.

- [ ] **INGEST-API-050**: The system shall fetch MGA bulk CSV or JSON from `mgaleg.maryland.gov/mgawebsite/Legislation/OpenData` for the current legislative session without authentication.
- [ ] **INGEST-API-051**: The system shall extract from each MGA bulk record: bill number, sponsor, chamber, synopsis, current status, committee assignments, hearing dates, and subject categories (up to 79 categories).
- [ ] **INGEST-API-052**: The system shall write each MGA bulk record to `bronze_documents` with `source` set to `"mga_bulk"` and `source_id` set to the bill number.
- [ ] **INGEST-API-053**: When an MGA bill already exists in bronze with an identical content_hash, the system shall skip the record without updating.
- [ ] **INGEST-API-054**: The system shall use the 79 MGA subject categories stored in `raw_metadata.subjects` to improve retrieval relevance for topic-filtered queries.

## ArcGIS Hub Clients [Phase 9]

- [ ] **INGEST-API-060**: The system shall query the Harford County ArcGIS Hub REST API (`harford-county-gis-hub-harfordgis.hub.arcgis.com`) for parcel, zoning, and land use layers.
- [ ] **INGEST-API-061**: The system shall query the Bel Air ArcGIS Hub REST API (`toba-data-hub-belairmd.hub.arcgis.com`) for zoning, property boundary, and public services layers.
- [ ] **INGEST-API-062**: ArcGIS feature records shall be written to `bronze_documents` with `source` set to `"arcgis_harford"` or `"arcgis_belair"` respectively.
- [ ] **INGEST-API-063**: ArcGIS geometry (GeoJSON) shall be stored in `raw_metadata.geometry`; spatial queries shall be possible by bounding box using the ArcGIS REST `geometry` parameter.

## Deprecated Sources

| Source | Status | Replacement |
|--------|--------|-------------|
| **ProPublica Congress API** | **DEFUNCT** (GitHub archived Feb 4, 2025) | `ingestion-federal` arrow → Congress.gov API |
| **Google Civic Information — Representatives** | **DEFUNCT** (April 30, 2025) | Cicero API or OCD-ID lookups |
