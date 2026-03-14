# Data Pipeline: Bronze → Silver → Gold

**Created**: 2026-03-14
**Status**: Design Phase
**HLD Reference**: §4.1 Medallion Architecture, §7 Data Model

## Context and Design Philosophy

The data pipeline transforms heterogeneous raw data from multiple government sources into a consistent, queryable data model. The core tension is between faithfulness to source data (Bronze) and usability for the chat and dashboard interfaces (Silver/Gold).

The guiding principle is **normalize late, preserve early**. Bronze stores everything the source provides, even fields we don't currently use. Silver extracts only what's needed for the current feature set. This means adding new dashboard features or chat capabilities rarely requires re-ingestion — just new normalization logic against existing Bronze data.

The pipeline is designed to be **fully idempotent**: running it twice produces the same Silver/Gold state. This means normalization can be re-run after fixing a bug without worrying about duplicate records or corrupted state.

## Normalization Architecture

### Source-Specific Normalizers

Each Bronze source has a dedicated normalizer function that maps source-specific fields to the unified Silver schema. The normalizer registry (`NORMALIZERS` dict) dispatches based on `bronze_documents.source`.

The normalizer pattern:
1. Read the `raw_content` JSON from Bronze
2. Extract and map fields to the target Pydantic model
3. Return a validated `LegislativeItem`, `CodeSection`, or `MeetingRecord`

Normalizers are pure functions (Bronze row in → Silver model out) with no side effects. This makes them independently testable without database access.

### Status Mapping

The most nuanced part of normalization is mapping source-specific status terminology to the unified `LegislativeStatus` enum. Each source uses different vocabulary:

**Open States** uses action classifications (verbs): "introduction", "referred-to-committee", "signed", "became-law". The normalizer examines the most recent action's classification list and maps the first recognized term.

**Bel Air legislation page** uses result labels (adjectives): "Approved", "Pending", "Tabled", "Expired", "Rejected". Direct 1:1 mapping.

**LegiScan** (Phase 2) uses numeric status codes: 1=Introduced, 2=Engrossed, 3=Enrolled, 4=Passed, 5=Vetoed, 6=Failed. Direct mapping with a lookup table.

**Harford County bills** (Phase 4) — status vocabulary unknown until scraper is built. The normalizer will need to be written against actual scraped data.

For unrecognized statuses, the fallback is always `UNKNOWN`. This is intentional — it's better to surface "unknown" in the dashboard than to silently misclassify.

### Jurisdiction Classification

State-level items are straightforward: everything from Open States and LegiScan is `STATE`. Municipal items from Bel Air scrapers are `MUNICIPAL`. County items from Harford scrapers are `COUNTY`.

The harder problem (deferred to post-MVP) is determining which state bills affect Harford County or Bel Air specifically. Many state bills are statewide, but some target specific counties or municipalities. The initial approach is to include all Maryland bills and let the user filter by jurisdiction in the dashboard. Smarter filtering (using bill text analysis or sponsor district matching) is a post-MVP enhancement.

### Deduplication

Open States and LegiScan may both have records for the same bill. Deduplication happens at the Silver layer using the `source_id` field (bill identifier like "HB 100") plus `jurisdiction` and `body` as a composite key. The upsert strategy:

- First write wins (whichever source runs first creates the Silver record)
- Subsequent writes update only if the new data is richer (has summary when existing doesn't, has more recent last_action_date)
- Both Bronze records are preserved — deduplication is at Silver, not Bronze

## Enrichment Pipeline

### LLM-Generated Summaries

Legislative text is dense and technical. The enrichment pipeline generates plain-language summaries for Silver records that lack them. This runs as a separate step after normalization:

1. Query Silver for `legislative_items` where `summary IS NULL`
2. For each, construct a prompt: "Summarize this bill title and available text in 2-3 sentences for a non-expert resident"
3. Call Gemini Flash (free tier) — summaries don't require frontier model capability
4. Write the summary back to the Silver record

Summary generation is expensive relative to normalization (one API call per item). It should run incrementally — only for new or updated items, not the full corpus.

### Topic Tagging

The `tags` array on `legislative_items` enables dashboard filtering by topic (zoning, taxes, public safety, education, etc.). Tags are generated via LLM classification:

1. Predefined tag taxonomy: `["zoning", "taxes", "public-safety", "education", "transportation", "environment", "housing", "business", "health", "budget", "elections", "utilities"]`
2. Prompt: "Classify this legislative item into 1-3 of these categories: {taxonomy}. Return only the category names."
3. Parse response, validate against taxonomy, write to `tags` array

Tag quality will vary — this is an area where user feedback could improve classification over time.

## Silver → Gold Materialization

The Gold layer doesn't require a separate materialization step for the dashboard — Silver tables are queried directly by the dashboard API. The Gold layer is exclusively the `document_chunks` table used by the RAG pipeline.

However, for dashboard performance, materialized views may become necessary:
- **Active legislation view**: Pre-filtered to `status NOT IN ('ENACTED', 'VETOED', 'EXPIRED', 'REJECTED')` across all jurisdictions
- **Recent changes view**: Items ordered by `last_action_date` with a 30-day window
- **Jurisdiction summary**: Count of items by jurisdiction × status for dashboard header stats

These are deferred until query performance demands them. At MVP scale (~2,500 Silver records), direct queries are fast enough.

## Data Quality and Freshness

### Validation Rules

Silver-layer validation is stricter than Bronze. Records must pass:
- `title` is non-empty and < 500 characters
- `jurisdiction` is a valid enum value
- `status` is a valid enum value (including UNKNOWN)
- `source_id` is non-empty
- `body` is non-empty and matches a known governing body name

Records failing validation are logged and skipped, not written to Silver. The Bronze record is preserved for debugging.

### Freshness Tracking

Every Silver record has `updated_at` (auto-set by trigger on update). The dashboard can display freshness indicators by comparing `max(updated_at)` per source against the current time:
- Green: updated within 24 hours
- Yellow: updated 24-72 hours ago
- Red: not updated in 72+ hours (likely a pipeline failure)

The `ingestion_runs` table provides a more granular view: last successful run per source, with failure details.

## Pipeline Execution

### Run Order

The pipeline runs in strict sequence:
1. **Normalization**: Bronze → Silver for all sources with new/changed Bronze records
2. **Enrichment**: Generate summaries and tags for Silver records missing them
3. **Embedding**: Chunk Silver records and generate Gold embeddings (covered in embeddings LLD)

Steps 2 and 3 can run in parallel since they don't depend on each other, but for simplicity, they run sequentially in the GitHub Actions workflow.

### Idempotency

Every pipeline step is idempotent:
- **Normalization**: Upsert by composite key — re-running produces identical Silver state
- **Enrichment**: Only processes records with `summary IS NULL` — already-enriched records are skipped
- **Embedding**: Checks for existing chunks before creating new ones (or deletes and recreates — simpler for MVP)

## Open Questions & Future Decisions

### Resolved
1. ✅ Source-specific normalizers over generic mapping — the source formats are too different for a one-size-fits-all approach
2. ✅ Deduplication at Silver, not Bronze — preserves source fidelity while preventing duplicate dashboard entries
3. ✅ UNKNOWN as default status — explicitly surfacing uncertainty over silent misclassification

### Deferred
1. State bill → local impact classification — which state bills specifically affect Harford County? Requires bill text analysis or district matching
2. Cross-reference resolution — linking `legislative_items` that amend specific `code_sections`
3. Change diffing — detecting what specifically changed in a code section between scrapes (beyond "it changed")
4. Materialized views for dashboard performance — unnecessary at MVP scale

## References

- Pydantic v2 docs: https://docs.pydantic.dev/latest/
- Supabase upsert: https://supabase.com/docs/reference/python/upsert
