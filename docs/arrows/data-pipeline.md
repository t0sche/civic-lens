# Arrow: data-pipeline

Bronze → Silver → Gold medallion transformation. Normalizes raw ingested data into the unified legislative_item and code_section schemas.

## Status

**PARTIALLY_IMPLEMENTED** - 2026-03-19. normalize.py fully implemented with 6 normalizer functions (openstates, belair_legislation, harford_bills, ecode360) and a NORMALIZERS registry. validate.py (DATA-PIPE-040-042) and enrich.py (DATA-PIPE-050-052, deferred) are not yet created.

## References

### HLD
- docs/high-level-design.md §4.1 (Medallion Architecture), §7 (Data Model)

### LLD
- docs/llds/data-pipeline.md (created 2026-03-14)

### EARS
- docs/specs/data-pipeline-specs.md (28 specs: 25 active, 3 deferred)

### Tests
- tests/pipeline/test_normalization.py
- tests/pipeline/test_silver_transforms.py (not yet created)

### Code
- src/pipeline/normalize.py — source-specific → Silver schema transforms (IMPLEMENTED)
- src/pipeline/enrich.py — LLM-generated summaries, tags, topic classification (NOT YET CREATED, deferred)
- src/pipeline/validate.py — data quality checks (NOT YET CREATED)

## Architecture

**Purpose:** Transform heterogeneous raw data from multiple sources into a consistent, queryable data model. The Silver layer is the single source of truth for both the dashboard (direct queries) and chat (via Gold embeddings).

**Key Components:**
1. Bronze → Silver normalizer — maps source-specific fields to legislative_item / code_section schemas
2. Enrichment pipeline — LLM-generated plain-language summaries, topic tags, jurisdiction classification
3. Silver → Gold materializer — generates dashboard-ready views (aggregations, status rollups)
4. Data quality validator — checks for missing fields, stale data, schema violations

## EARS Coverage

See spec file in References above.

## Key Findings

- normalize.py implements all 4 source normalizers: normalize_openstates_bill, normalize_belair_legislation, normalize_harford_bills, normalize_ecode360_section.
- NORMALIZERS registry maps source keys to normalizer functions; run_normalization supports per-source filtering (DATA-PIPE-060/061 verified).
- harford_bills normalizer uses case-insensitive prefix matching as a fallback for status mapping — robust against minor status string variation.
- validate.py is absent: Silver records can be written with empty titles, source_ids, or body values (DATA-PIPE-040/041/042 not yet enforced).
- enrich.py is absent and correctly deferred to Phase 9 (DATA-PIPE-050/051/052).

## Work Required

### Must Fix
1. Create src/pipeline/validate.py: reject Silver records with empty title (>500 chars), empty source_id, or empty body (DATA-PIPE-040/041/042).

### Should Fix
1. Add tests/pipeline/test_silver_transforms.py covering normalize_harford_bills, Silver upsert logic, and source filter behavior.
2. Deduplication across sources (same bill from Open States + LegiScan).

### Nice to Have
1. LLM enrichment: plain-language summaries, topic tagging (deferred to Phase 9).
2. Change detection — diff Silver records across runs, flag substantive changes.
3. Cross-reference resolution — link legislative_items to code_sections they would amend.
