# Arrow: data-pipeline

Bronze → Silver → Gold medallion transformation. Normalizes raw ingested data into the unified legislative_item and code_section schemas.

## Status

**MAPPED** - 2026-03-14. Data model defined in HLD §7; transformation logic not yet built.

## References

### HLD
- docs/high-level-design.md §4.1 (Medallion Architecture), §7 (Data Model)

### LLD
- docs/llds/data-pipeline.md (created 2026-03-14)

### EARS
- docs/specs/data-pipeline-specs.md (25 specs: 22 active, 3 deferred)

### Tests
- tests/pipeline/test_normalization.py
- tests/pipeline/test_silver_transforms.py

### Code
- src/pipeline/normalize.py — source-specific → Silver schema transforms
- src/pipeline/enrich.py — LLM-generated summaries, tags, topic classification
- src/pipeline/validate.py — data quality checks

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

None yet — UNMAPPED.

## Work Required

### Must Fix
1. Source-specific normalizers: Open States → legislative_item, eCode360 → code_section
2. Status mapping logic (source-specific statuses → unified enum)
3. Jurisdiction classification (which state bills affect Harford County / Bel Air?)
4. Data freshness tracking (last_updated timestamps, staleness detection)

### Should Fix
1. LLM enrichment: plain-language summaries for bills and code sections
2. Topic tagging for dashboard filtering (zoning, taxes, public safety, etc.)
3. Deduplication across sources (same bill from Open States + LegiScan)

### Nice to Have
1. Change detection — diff Silver records across runs, flag substantive changes
2. Cross-reference resolution — link legislative_items to code_sections they would amend
