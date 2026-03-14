# Ingestion: API Clients

**Created**: 2026-03-14
**Status**: Design Phase
**HLD Reference**: §4.3 Tier 1, §5 D1 (Open States over MGA scraping)

## Context and Design Philosophy

Tier 1 data sources are structured APIs that provide reliable, well-formatted data with minimal maintenance burden. These are the backbone of the ingestion layer — if nothing else works, state legislative data from Open States and LegiScan keeps the platform useful.

The design philosophy is **defensive ingestion**: every API call assumes failure is possible, every response is validated before writing, and every run is tracked in `ingestion_runs` for observability. Idempotent writes via content hashing mean re-running a client is always safe.

## Open States Client

### API Contract

Open States v3 is a REST API (not GraphQL despite some docs suggesting it). The Maryland jurisdiction ID is `ocd-jurisdiction/country:us/state:md/government`.

Key endpoints:
- `GET /bills` — paginated bill listing with filters (session, updated_since, classification)
- `GET /bills/{id}` — full bill detail with actions, sponsorships, abstracts, sources

The `include` parameter controls which nested objects are returned. For our use case, we request `abstracts,actions,sponsorships,sources` — this gives us everything needed for Silver layer normalization in a single request per bill.

Pagination follows a `page` + `per_page` pattern (max 50 per page). The `pagination.max_page` field in the response tells us when to stop.

### Rate Limiting and Error Handling

Open States does not publish explicit rate limits but recommends "reasonable use." The client enforces a self-imposed rate limit by processing responses synchronously — no concurrent requests. At 50 bills per page and typical session sizes of 2,000-3,000 bills, a full session fetch takes ~60 pages × ~1 second per request = ~1 minute.

Error handling strategy:
- **HTTP 429 (rate limited)**: Exponential backoff with 3 retries, starting at 5 seconds
- **HTTP 5xx**: Retry once after 10 seconds, then fail the run
- **HTTP 4xx (not 429)**: Fail immediately (likely a code bug, not transient)
- **Network timeout**: 30-second timeout per request, retry once

All errors are logged and recorded in `ingestion_runs.error_message`.

### Incremental Fetching

The `updated_since` parameter is the key to efficient incremental fetching. On each run, the client queries for bills updated since the last successful run's `started_at` timestamp (read from `ingestion_runs`). On the first run (no previous run), it fetches the entire current session.

This reduces API calls from ~60 pages (full session) to typically 1-3 pages (bills updated in the last 6 hours).

### Bronze Layer Writing

Each bill is serialized as the full JSON response body and written to `bronze_documents` with:
- `source`: `"openstates"`
- `source_id`: The Open States bill ID (e.g., `"ocd-bill/abc-123"`)
- `document_type`: `"bill"`
- `raw_content`: Full JSON string
- `raw_metadata`: Extracted convenience fields (identifier, session, classification)
- `url`: The Open States public URL for the bill
- `content_hash`: SHA-256 of the raw JSON

The `content_hash` enables change detection — if a bill hasn't changed since the last fetch, the upsert is a no-op (same hash, no update triggered).

## LegiScan Client

### Complementary Role

LegiScan serves two purposes: supplementary data (full bill text, roll call vote details, amendment tracking) and fallback if Open States has availability issues. The clients are designed to run independently — deduplication happens in the Silver normalization layer, not at ingestion time.

### API Contract

LegiScan uses a single endpoint (`https://api.legiscan.com`) with operation-based routing via the `op` parameter:
- `getSessionList` — available Maryland sessions
- `getMasterList` — all bills in a session (summary metadata)
- `getBill` — full bill detail (history, sponsors, texts, votes)
- `getBillText` — full text of a bill document (base64-encoded)
- `search` — keyword search across bills

The `getMasterList` → `getBill` pattern is the primary collection flow: get the list of all bill IDs in the current session, then fetch full detail for each.

### Rate Limiting

Free tier: 30,000 queries/month. A full session fetch at ~3,000 bills costs ~3,001 queries (1 master list + 3,000 detail fetches). Monthly runs of the full pipeline (assuming 4 sessions worth of incremental updates) should stay well under the limit.

The client tracks query count per run and logs a warning at 80% of the monthly budget.

### Bronze Layer Writing

Same pattern as Open States: full bill detail JSON serialized to `bronze_documents` with `source = "legiscan"` and `source_id` as the LegiScan bill ID (numeric).

## ArcGIS Hub Client (Deferred to Phase 4)

Harford County's ArcGIS Hub provides zoning, parcel, and land use data via standard ArcGIS REST endpoints. These are valuable for contextual enrichment (e.g., answering "what zone is my property in?") but are not core legislative data.

The client will use the ArcGIS REST API's `query` endpoint to fetch GeoJSON features, writing them to Bronze with `source = "arcgis_harford"`. No custom scraping needed — the API returns structured data directly.

## YouTube Data API Client (Deferred to Phase 4)

Bel Air meeting videos are archived on YouTube. The YouTube Data API provides video metadata and auto-generated captions. Captions are the highest-value data (searchable meeting content), but caption quality from auto-generation is variable.

The client will:
1. List videos from the Town of Bel Air channel
2. Fetch video metadata (title, date, description)
3. Download auto-generated captions (SRT/VTT format)
4. Write caption text to Bronze for downstream processing

## Data Quality Validation

Before writing to Bronze, each client performs minimal validation:
- **Non-empty content**: Reject records with empty or whitespace-only raw content
- **Required fields**: Reject records missing source_id or document_type
- **Size sanity**: Log warnings for unusually large (>1MB) or small (<10 bytes) documents

Validation is intentionally minimal at the Bronze layer — the philosophy is "store everything, validate at normalization." Bronze is a faithful mirror of source data, warts and all.

## Open Questions & Future Decisions

### Resolved
1. ✅ Open States as primary, LegiScan as supplementary — Open States has better data freshness; LegiScan has better bill text coverage
2. ✅ Full JSON serialization to Bronze — preserves all source data; normalization extracts what's needed

### Deferred
1. Bill text extraction from LegiScan (base64-encoded documents) — needed for full-text search, deferred until search quality demands it
2. ArcGIS and YouTube clients — Phase 4 enrichment, not core legislative data
3. Concurrent API fetching — unnecessary at current volume; add if ingestion runtime exceeds 15 minutes

## References

- Open States API v3 docs: https://docs.openstates.org/api-v3/
- LegiScan API docs: https://legiscan.com/legiscan
- ArcGIS REST API: https://developers.arcgis.com/rest/
