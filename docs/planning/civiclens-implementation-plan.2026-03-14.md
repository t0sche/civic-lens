# CivicLens Implementation Plan

**Created**: 2026-03-14
**Owner**: Stephen Shaffer
**Status**: Phase 8 In Progress (Phases 1–7 complete, deployed 2026-03-17)
**Design Doc**: `/docs/high-level-design.md`, `/docs/llds/*.md`
**EARS Specs**: `/docs/specs/*.md`

## Overview

Phased implementation of CivicLens — a civic transparency platform for Bel Air, MD (21015). The plan follows the arrow dependency chain: infrastructure first, then ingestion, pipeline, and finally the two user-facing surfaces (chat and dashboard) in parallel.

Each phase has a concrete milestone that proves the system works at that layer before building the next. The plan assumes evening/weekend time from a solo developer — phases are scoped to be completable in focused multi-hour sessions, not sustained full-time weeks.

## Success Criteria

1. A resident can ask "What are the fence regulations in Bel Air?" and receive a sourced, cited answer within 30 seconds
2. The dashboard shows active Maryland state bills and Bel Air town legislation with status and jurisdiction filtering
3. The ingestion pipeline runs unattended on a 6-hour / daily schedule via GitHub Actions without manual intervention
4. Monthly operating cost stays under $10 at low traffic (<1,000 monthly users)
5. The repository is cloneable and deployable by another developer following the README

---

## Phase 1: Foundation

**Goal**: Standing infrastructure — database with schemas, deployed frontend shell, working environment config. After this phase, every subsequent phase has somewhere to write data and somewhere to serve it.

### Deliverables

1. **Supabase project setup**
   - **Specs**: INFRA-DB-001 through INFRA-DB-008, INFRA-SEC-001 through INFRA-SEC-003
   - Create Supabase project, enable pgvector extension
   - Run `001_initial_schema.sql` migration (Bronze/Silver/Gold tables, enums, indexes, triggers)
   - Run `002_vector_search_rpc.sql` migration (similarity search function)
   - Configure RLS policies (anon SELECT, service_role write)
   - Verify schema via Supabase dashboard table inspector

2. **Environment and configuration**
   - **Specs**: INFRA-ENV-001 through INFRA-ENV-004
   - Procure API keys: Open States, LegiScan, Google AI (Gemini), Anthropic
   - Fill `.env.local` from `.env.example`
   - Verify `src/lib/config.py` loads all variables correctly
   - Verify missing variable raises clear error (INFRA-ENV-003)

3. **Vercel deployment**
   - **Specs**: DASH-NAV-001, DASH-NAV-002, DASH-NAV-003
   - Connect GitHub repo to Vercel
   - Set environment variables in Vercel dashboard
   - Deploy the Next.js shell (layout, navigation, empty dashboard, about page)
   - Verify the site loads at the Vercel URL with nav, footer, and legal disclaimers

4. **Supabase client verification**
   - **Specs**: INFRA-CLIENT-001, INFRA-CLIENT-002, INFRA-CLIENT-003
   - Test Python `get_supabase_client()` — connect and run a test query locally
   - Test TypeScript `createServerClient()` — verify Vercel API route can query Supabase
   - Test TypeScript `createBrowserClient()` — verify anon key allows SELECT from frontend

### Testing Requirements

- ✅ **INFRA-DB-001 through INFRA-DB-006**: Tables exist with correct columns and constraints (manual verification via Supabase dashboard + test INSERT/SELECT)
- ✅ **INFRA-DB-007**: Update trigger fires (UPDATE a row, verify updated_at changed)
- ✅ **INFRA-DB-008**: match_document_chunks function exists (call with dummy embedding, expect empty result)
- ✅ **INFRA-SEC-001**: Anon key can SELECT from legislative_items
- ✅ **INFRA-SEC-002**: Anon key cannot INSERT into legislative_items
- ✅ **INFRA-ENV-003**: Missing SUPABASE_URL raises descriptive error
- ✅ **INFRA-CLIENT-001**: Python client connects and queries successfully
- ✅ **DASH-NAV-001**: Navigation links render on deployed site

### Definition of Done

- [x] Supabase project created with pgvector enabled
- [x] Both migrations applied successfully
- [x] RLS policies configured and tested (anon read, service_role write)
- [x] All API keys procured and stored in `.env.local` and Vercel
- [x] Python config module loads all environment variables
- [x] Next.js app deployed to Vercel with working navigation, footer, disclaimers
- [x] Python Supabase client can connect and query from local machine
- [x] TypeScript server client can query from Vercel API route

---

## Phase 2: State Bill Ingestion

**Goal**: Maryland state bills flowing from Open States API into Bronze and Silver layers. After this phase, the pipeline's core loop (fetch → store → normalize) is proven with the highest-quality data source.

### Deliverables

1. **Open States API client**
   - **Specs**: INGEST-API-001 through INGEST-API-008, INGEST-API-020 through INGEST-API-023, INGEST-API-030 through INGEST-API-032, INGEST-API-040, INGEST-API-041
   - Run `python -m src.ingestion.clients.openstates` locally
   - Verify bills are written to bronze_documents with correct source, source_id, content_hash
   - Verify ingestion_runs row tracks the run (started, completed, counts)
   - Verify incremental fetch with `updated_since` returns fewer results than full fetch

2. **Open States normalization**
   - **Specs**: DATA-PIPE-001 through DATA-PIPE-007, DATA-PIPE-030, DATA-PIPE-040 through DATA-PIPE-042, DATA-PIPE-060, DATA-PIPE-061
   - Run `python -m src.pipeline.normalize --source openstates`
   - Verify legislative_items rows have correct jurisdiction (STATE), body, status mapping, sponsors, summary
   - Verify idempotency — run normalization twice, check same Silver state

3. **Unit tests passing**
   - **Specs**: Covered by test files
   - `pytest tests/ingestion/test_openstates.py` — all 6 tests pass
   - `pytest tests/pipeline/test_normalization.py::TestNormalizeOpenStatesBill` — all 7 tests pass

### Testing Requirements

- ✅ **INGEST-API-001**: Client fetches from correct jurisdiction
- ✅ **INGEST-API-003**: Pagination follows all pages
- ✅ **INGEST-API-005**: API key sent in header
- ✅ **INGEST-API-008**: HTTP 4xx raises immediately
- ✅ **INGEST-API-020**: Bills written to bronze_documents with source="openstates"
- ✅ **INGEST-API-021**: content_hash is SHA-256 of raw_content
- ✅ **INGEST-API-030 through INGEST-API-032**: Run tracking works (start, success, failure)
- ✅ **DATA-PIPE-001 through DATA-PIPE-007**: All normalization field mappings correct
- ✅ **DATA-PIPE-061**: Running normalization twice produces identical Silver state

### Definition of Done

- [x] `python -m src.ingestion.clients.openstates` fetches MD bills and writes to Bronze
- [x] `python -m src.pipeline.normalize` normalizes Bronze → Silver with correct field mapping
- [x] `pytest tests/ingestion/test_openstates.py` — 6/6 passing
- [x] `pytest tests/pipeline/test_normalization.py::TestNormalizeOpenStatesBill` — 7/7 passing
- [x] Supabase dashboard shows legislative_items with STATUS, jurisdiction, sponsors populated
- [x] Running the full pipeline twice produces no duplicates (idempotent)
- [x] ingestion_runs table tracks successful run with record counts

---

## Phase 3: Town Code Ingestion

**Goal**: Bel Air town code and legislation flowing into Bronze and Silver. This is the highest-value local data source and proves the scraping infrastructure.

### Deliverables

1. **eCode360 scraper (Bel Air)**
   - **Specs**: INGEST-SCRAPE-001 through INGEST-SCRAPE-008
   - Run `python -m src.ingestion.scrapers.ecode360` locally
   - Verify TOC extraction finds chapters
   - Verify section extraction produces content with hierarchy metadata
   - Verify polite crawling (1s delay, honest User-Agent)
   - Verify Bronze writes with source="ecode360_belair"

2. **Bel Air legislation page scraper**
   - **Specs**: INGEST-SCRAPE-010 through INGEST-SCRAPE-015
   - Run `python -m src.ingestion.scrapers.belair_legislation` locally
   - Verify ordinances and resolutions extracted with status, type, PDF links
   - Verify Bronze writes with source="belair_legislation"

3. **eCode360 and Bel Air legislation normalization**
   - **Specs**: DATA-PIPE-010 through DATA-PIPE-012, DATA-PIPE-020 through DATA-PIPE-023, DATA-PIPE-031
   - Run `python -m src.pipeline.normalize`
   - Verify code_sections populated with correct jurisdiction (MUNICIPAL), code_source, section_path
   - Verify legislative_items populated with MUNICIPAL jurisdiction, correct status mapping

4. **Change detection**
   - **Specs**: INGEST-SCRAPE-020, INGEST-SCRAPE-021
   - Run scraper twice, verify content_hash prevents unnecessary updates
   - Verify ingestion_runs tracks both runs

5. **Unit tests passing**
   - `pytest tests/pipeline/test_normalization.py::TestNormalizeBelairLegislation` — 2/2 passing
   - `pytest tests/pipeline/test_normalization.py::TestNormalizeEcode360Section` — 2/2 passing

### Testing Requirements

- ✅ **INGEST-SCRAPE-001**: TOC page returns chapter entries
- ✅ **INGEST-SCRAPE-002**: Chapter pages yield section-level content
- ✅ **INGEST-SCRAPE-004**: Hierarchy metadata (chapter, section_title, level, municipality_code) present
- ✅ **INGEST-SCRAPE-005**: Request delay ≥1 second between fetches (verify via timing or mock)
- ✅ **INGEST-SCRAPE-010**: Legislation page returns entries
- ✅ **INGEST-SCRAPE-012**: Entries correctly classified as ordinance or resolution
- ✅ **INGEST-SCRAPE-013**: Status labels mapped correctly
- ✅ **DATA-PIPE-020 through DATA-PIPE-023**: eCode360 normalization produces correct jurisdiction, code_source, section_path
- ✅ **DATA-PIPE-010 through DATA-PIPE-012**: Bel Air legislation normalization produces correct jurisdiction, body, status

### Definition of Done

- [x] eCode360 scraper extracts Bel Air town code chapters and sections into Bronze
- [x] Bel Air legislation scraper extracts ordinances/resolutions into Bronze
- [x] Normalization produces code_sections and legislative_items in Silver
- [x] section_path breadcrumbs are correct (e.g., "Town of Bel Air Code > Chapter 165 > §165-23")
- [x] Change detection works — second run skips unchanged content
- [x] All normalization unit tests passing (4/4)
- [x] Supabase shows populated code_sections and municipal legislative_items

---

## Phase 4: Embeddings and RAG

**Goal**: Documents are chunked, embedded, and retrievable via vector search. The RAG pipeline can answer a question using retrieved context. This is the technical core of the chat feature.

### Deliverables

1. **Section-aware chunking**
   - **Specs**: EMBED-CHUNK-001 through EMBED-CHUNK-006, EMBED-CHUNK-010 through EMBED-CHUNK-012
   - Run chunking on code_sections and legislative_items
   - Verify short sections produce single chunks, long sections produce overlapping sub-chunks
   - Verify section_path and jurisdiction propagate to every chunk

2. **Embedding generation**
   - **Specs**: EMBED-GEN-001 through EMBED-GEN-004
   - Run `python -m src.pipeline.embedder` locally
   - Verify document_chunks table populated with embeddings
   - Verify embedding dimensions match model (768 for Gemini)

3. **Vector search verification**
   - **Specs**: EMBED-SEARCH-001 through EMBED-SEARCH-003
   - Call match_document_chunks with a test query embedding
   - Verify results are returned ordered by similarity
   - Verify jurisdiction filter narrows results correctly

4. **RAG pipeline integration**
   - **Specs**: CHAT-RAG-001 through CHAT-RAG-004
   - Call the retrieval pipeline from TypeScript (embed query → search pgvector → get chunks)
   - Verify prompt construction includes numbered sources with section_path and jurisdiction

5. **Unit tests passing**
   - `pytest tests/pipeline/test_chunking.py` — all 7 tests pass

### Testing Requirements

- ✅ **EMBED-CHUNK-001**: Short section → single chunk with full_section: true
- ✅ **EMBED-CHUNK-002**: Long section → multiple sub-chunks
- ✅ **EMBED-CHUNK-003**: Sub-chunks have 200-char overlap
- ✅ **EMBED-CHUNK-004**: Sequential chunk_index values
- ✅ **EMBED-CHUNK-010**: Legislative item → single chunk with title + summary
- ✅ **EMBED-CHUNK-011**: Legislative item without summary → metadata has_summary: false
- ✅ **EMBED-CHUNK-012**: Section path includes body name
- ✅ **EMBED-GEN-001**: Gemini embedding returns 768-dimensional vector
- ✅ **EMBED-SEARCH-001**: match_document_chunks returns results ordered by similarity
- ✅ **EMBED-SEARCH-002**: Jurisdiction filter narrows results

### Definition of Done

- [x] `python -m src.pipeline.embedder` populates document_chunks with embeddings
- [x] `pytest tests/pipeline/test_chunking.py` — 7/7 passing
- [x] Querying match_document_chunks with "fence regulations" returns relevant town code chunks
- [x] Jurisdiction filter (MUNICIPAL only) excludes state bill chunks
- [x] RAG retrieval pipeline returns formatted context with source citations
- [x] Document chunk count matches expected: ~1 chunk per code_section + ~1 per legislative_item

---

## Phase 5: Chat Interface

**Goal**: A working chat that residents can use. Question in, sourced answer out, with model routing and legal disclaimers.

### Deliverables

1. **Model routing**
   - **Specs**: CHAT-ROUTE-001 through CHAT-ROUTE-005
   - Verify simple queries route to Gemini Flash (free)
   - Verify complex queries (multi-jurisdiction, impact analysis) route to Claude Sonnet
   - Verify routing decision included in API response

2. **Chat API route**
   - **Specs**: CHAT-API-001 through CHAT-API-005, CHAT-MODEL-001 through CHAT-MODEL-003
   - POST to /api/chat with a test question
   - Verify response contains answer, sources, model, tier
   - Verify empty message returns 400
   - Verify oversized message returns 400
   - Verify API errors return 500 with detail

3. **System prompt and citations**
   - **Specs**: CHAT-RAG-010 through CHAT-RAG-015
   - Verify answers cite sources with [Source N] notation
   - Verify legal disclaimer appears at the end of substantive answers
   - Verify "I don't know" response when no relevant chunks exist

4. **Chat UI**
   - **Specs**: CHAT-UI-001 through CHAT-UI-008
   - Deploy chat page to Vercel
   - Verify example questions render and are clickable
   - Verify loading indicator shows during processing
   - Verify source citations display below assistant messages
   - Verify model tier badge appears
   - Verify permanent disclaimer at bottom of input

### Testing Requirements

- ✅ **CHAT-ROUTE-001**: Query spanning 3+ documents → frontier
- ✅ **CHAT-ROUTE-002**: Multi-jurisdiction results → frontier
- ✅ **CHAT-ROUTE-003**: "how does X affect Y" pattern → frontier
- ✅ **CHAT-ROUTE-004**: Simple single-jurisdiction query → free
- ✅ **CHAT-API-002**: Empty message → 400
- ✅ **CHAT-API-003**: 2001-character message → 400
- ✅ **CHAT-RAG-014**: Response ends with legal disclaimer
- ✅ **CHAT-UI-002**: 4 example questions displayed
- ✅ **CHAT-UI-004**: Loading indicator visible during processing
- ✅ **CHAT-UI-007**: Permanent disclaimer visible below input

### Definition of Done

- [x] "What are the fence regulations in Bel Air?" returns a sourced, cited answer
- [x] Simple queries use Gemini Flash; complex queries use Claude Sonnet
- [x] Empty/oversized messages are rejected with appropriate HTTP errors
- [x] Legal disclaimer appears at the end of every substantive answer
- [x] "What is the federal tax rate?" returns "I don't have information about that" (not in corpus)
- [x] Chat UI deployed to Vercel with example questions, citations, loading state
- [x] Model tier indicator shows on each response
- [x] End-to-end latency under 10 seconds for Gemini Flash queries

---

## Phase 6: Dashboard

**Goal**: A populated legislative tracker with jurisdiction filtering. Residents can see what's happening across all government layers.

### Deliverables

1. **Dashboard page**
   - **Specs**: DASH-VIEW-001 through DASH-VIEW-004
   - Verify dashboard renders with legislative_items from Supabase
   - Verify default ordering by last_action_date descending
   - Verify 50-item limit

2. **Filter bar**
   - **Specs**: DASH-FILTER-001 through DASH-FILTER-003
   - Verify jurisdiction buttons render (All, State, County, Municipal)
   - Verify active filter is visually distinguished
   - Verify filter URLs are bookmarkable (`/?jurisdiction=STATE`)

3. **Legislative item cards**
   - **Specs**: DASH-CARD-001 through DASH-CARD-006
   - Verify jurisdiction badge colors (purple/teal/sky)
   - Verify status badge colors (green/blue/yellow/red/amber/orange/gray)
   - Verify source_id, title (linked), summary, metadata row render correctly

4. **Empty state**
   - **Specs**: DASH-EMPTY-001, DASH-EMPTY-002
   - Verify empty state renders when no items match filter

5. **About page**
   - **Specs**: DASH-ABOUT-001, DASH-ABOUT-002
   - Verify about page describes project, data sources, disclaimers
   - Verify COMAR exclusion note is present

### Testing Requirements

- ✅ **DASH-VIEW-001**: Page renders with items ordered by last_action_date desc
- ✅ **DASH-VIEW-002**: `?jurisdiction=STATE` shows only state items
- ✅ **DASH-VIEW-003**: No parameter shows all jurisdictions
- ✅ **DASH-VIEW-004**: Invalid jurisdiction defaults to ALL
- ✅ **DASH-FILTER-002**: Active filter button has dark background
- ✅ **DASH-CARD-001**: State items show purple badge, municipal show sky blue
- ✅ **DASH-CARD-002**: ENACTED items show green badge, PENDING shows amber
- ✅ **DASH-CARD-004**: Title links to source_url in new tab
- ✅ **DASH-EMPTY-001**: Empty state message appears when no items exist
- ✅ **DASH-ABOUT-002**: COMAR exclusion note present on about page

### Definition of Done

- [x] Dashboard shows state bills + town legislation with correct badges and ordering
- [x] Jurisdiction filter works (URL-based, bookmarkable, visual indicator)
- [x] Status colors are correct across all status types
- [x] Titles link to source documents
- [x] Empty state renders correctly when filtering to an unpopulated jurisdiction (COUNTY before Phase 8)
- [x] About page deployed with all disclaimers and data source attributions
- [x] Dashboard deployed to Vercel at the root URL

---

## Phase 7: Automation

**Goal**: The pipeline runs unattended. Data stays fresh without manual intervention. Failures are detected.

### Deliverables

1. **GitHub Actions workflows**
   - **Specs**: INFRA-CI-001 through INFRA-CI-005
   - Configure repository secrets in GitHub
   - Push `.github/workflows/ingest.yml` and verify it triggers
   - Verify state bill ingestion runs on 6-hour cron
   - Verify local scraping runs on daily cron
   - Verify normalization + embedding runs after ingestion
   - Verify manual dispatch works with source selector

2. **Failure alerting**
   - **Specs**: INFRA-CI-004
   - Simulate a failure (bad API key) and verify notify-on-failure job runs
   - Verify ingestion_runs table shows failed run with error message
   - Enable GitHub email notifications for failed workflows

3. **End-to-end unattended test**
   - Let the pipeline run for 48 hours unattended
   - Verify data freshness in Supabase (new runs logged, data updated)
   - Verify no silent failures (all runs either success or detected failure)

### Testing Requirements

- ✅ **INFRA-CI-001**: State bill ingestion runs every 6 hours (check Actions run history)
- ✅ **INFRA-CI-002**: Local scraping runs daily at 11:00 UTC (check cron trigger)
- ✅ **INFRA-CI-003**: Normalization runs after successful ingestion
- ✅ **INFRA-CI-004**: Failed job triggers notify-on-failure
- ✅ **INFRA-CI-005**: Manual dispatch with source="openstates" runs only that source
- ✅ **INGEST-API-032**: Failed ingestion run recorded in ingestion_runs with error message

### Definition of Done

- [x] GitHub Actions secrets configured (6 secrets)
- [x] Workflow runs successfully on push (manual dispatch test)
- [x] Cron schedule verified — at least one automated state bill run observed
- [x] Failure alerting works — simulated failure produces notification
- [x] Pipeline runs unattended for 48 hours with no silent failures
- [x] ingestion_runs table shows healthy run history

---

## Phase 8: County Expansion

**Goal**: Harford County data added — county code from eCode360 and county council legislation from the custom bills tracker.

### Deliverables

1. **Harford County code (eCode360)**
   - **Specs**: INGEST-SCRAPE-008, DATA-PIPE-021
   - Run eCode360 scraper with municipality_code="HA0904"
   - Verify Bronze writes with source="ecode360_harford"
   - Verify Silver code_sections with jurisdiction=COUNTY

2. **Harford County bills tracker scraper**
   - **Specs**: INGEST-SCRAPE-040, INGEST-SCRAPE-041 (currently deferred — promote to active)
   - Reverse-engineer the ASP.NET application request flow
   - Build scraper with session/ViewState handling
   - Write county council bills to Bronze

3. **County normalization and embedding**
   - Normalize county code sections and bills to Silver
   - Generate embeddings for county content
   - Verify county items appear in dashboard with COUNTY jurisdiction
   - Verify county content is retrievable in chat

### Definition of Done

- [ ] Harford County code sections in Silver with correct jurisdiction and section_path
- [ ] County council bills in Silver (or documented as blocked by ASP.NET complexity)
- [ ] County items appear in dashboard with teal badges
- [ ] Chat can answer questions about county regulations
- [ ] Dashboard COUNTY filter shows populated results

---

## Phase 9: Hardening

**Goal**: The system is reliable, observable, and ready for public use.

### Deliverables

1. **Data freshness indicators**
   - **Specs**: DASH-FRESH-001 (promote from deferred)
   - Dashboard header shows last-updated per source with color coding

2. **Response quality evaluation**
   - **Specs**: EMBED-EVAL-001, EMBED-EVAL-002 (promote from deferred)
   - Create 20-question test set with expected source sections
   - Measure recall@8 and tune similarity threshold if needed

3. **LegiScan integration**
   - **Specs**: INGEST-API-010 through INGEST-API-013
   - Run LegiScan client as supplementary data source
   - Verify deduplication in Silver layer

4. **Cost monitoring**
   - Track Claude API usage and embedding API calls
   - Verify monthly cost stays under $10

5. **Documentation for forkability**
   - Update README with complete setup instructions
   - Document how to configure for a different jurisdiction
   - Ensure all environment variables are documented

### Definition of Done

- [ ] Freshness indicators visible on dashboard
- [ ] Retrieval quality test set achieves ≥80% recall@8
- [ ] LegiScan running as supplementary source without duplicates
- [ ] Monthly cost verified under $10
- [ ] README enables another developer to deploy for their jurisdiction
- [ ] System has run unattended for 2 weeks with acceptable data freshness

---

## Requirements Traceability

### Phase 1 (Foundation)
- Infrastructure: INFRA-DB-001 through INFRA-DB-008, INFRA-SEC-001 through INFRA-SEC-003, INFRA-ENV-001 through INFRA-ENV-004, INFRA-CLIENT-001 through INFRA-CLIENT-003
- Dashboard (shell only): DASH-NAV-001 through DASH-NAV-003
**Total Phase 1 Requirements**: 23

### Phase 2 (State Bill Ingestion)
- Ingestion APIs: INGEST-API-001 through INGEST-API-008, INGEST-API-020 through INGEST-API-023, INGEST-API-030 through INGEST-API-032, INGEST-API-040, INGEST-API-041
- Data Pipeline: DATA-PIPE-001 through DATA-PIPE-007, DATA-PIPE-030, DATA-PIPE-040 through DATA-PIPE-042, DATA-PIPE-060, DATA-PIPE-061
**Total Phase 2 Requirements**: 28

### Phase 3 (Town Code Ingestion)
- Ingestion Scraping: INGEST-SCRAPE-001 through INGEST-SCRAPE-008, INGEST-SCRAPE-010 through INGEST-SCRAPE-015, INGEST-SCRAPE-020, INGEST-SCRAPE-021
- Data Pipeline: DATA-PIPE-010 through DATA-PIPE-012, DATA-PIPE-020 through DATA-PIPE-023, DATA-PIPE-031
**Total Phase 3 Requirements**: 23

### Phase 4 (Embeddings and RAG)
- Embeddings: EMBED-CHUNK-001 through EMBED-CHUNK-006, EMBED-CHUNK-010 through EMBED-CHUNK-012, EMBED-GEN-001 through EMBED-GEN-004, EMBED-WRITE-001 through EMBED-WRITE-003, EMBED-SEARCH-001 through EMBED-SEARCH-003
- Chat (retrieval only): CHAT-RAG-001 through CHAT-RAG-004
**Total Phase 4 Requirements**: 22

### Phase 5 (Chat Interface)
- Chat: CHAT-RAG-010 through CHAT-RAG-015, CHAT-ROUTE-001 through CHAT-ROUTE-005, CHAT-API-001 through CHAT-API-005, CHAT-MODEL-001 through CHAT-MODEL-003, CHAT-UI-001 through CHAT-UI-008
**Total Phase 5 Requirements**: 27

### Phase 6 (Dashboard)
- Dashboard: DASH-VIEW-001 through DASH-VIEW-004, DASH-FILTER-001 through DASH-FILTER-003, DASH-CARD-001 through DASH-CARD-006, DASH-EMPTY-001, DASH-EMPTY-002, DASH-ABOUT-001, DASH-ABOUT-002
**Total Phase 6 Requirements**: 17

### Phase 7 (Automation)
- Infrastructure CI: INFRA-CI-001 through INFRA-CI-005
**Total Phase 7 Requirements**: 5

### Phase 8 (County Expansion)
- Promoted from deferred: INGEST-SCRAPE-040, INGEST-SCRAPE-041
- Reuses existing: INGEST-SCRAPE-008, DATA-PIPE-021
**Total Phase 8 Requirements**: 4

### Phase 9 (Hardening)
- Promoted from deferred: DASH-FRESH-001, EMBED-EVAL-001, EMBED-EVAL-002
- Ingestion APIs: INGEST-API-010 through INGEST-API-013
**Total Phase 9 Requirements**: 7

**Grand Total**: 156 active requirements across 9 phases (covers all 152 active specs + 4 promoted from deferred)

---

## Risk Assessment

### High Risk

**1. eCode360 HTML structure doesn't match scraper assumptions**
- **Likelihood**: Medium — eCode360 is a stable platform but HTML varies across municipalities
- **Mitigation**: Build scraper with fallback cascade (section elements → headings → full chapter). Test against live site before committing to the approach.
- **Fallback**: Pay for eCode360 API ($250 setup + $595/year) if HTML scraping proves unreliable.

**2. Vercel 10-second serverless timeout for Claude API calls**
- **Likelihood**: Medium — Claude Sonnet typically responds in 3-8s, but can spike
- **Mitigation**: Route only truly complex queries to Claude (strict routing heuristic). Most queries hit Gemini Flash (<3s).
- **Fallback**: Enable Vercel streaming responses (resets timeout per chunk) or upgrade to Vercel Pro ($20/month, 60s timeout).

### Medium Risk

**3. Supabase 500MB free tier exhaustion**
- **Likelihood**: Low for MVP, increasing with Phase 8 (county data) and PDF extraction
- **Mitigation**: Monitor storage via Supabase dashboard. Bronze layer is the biggest consumer — can move raw content to Supabase Storage if needed.
- **Fallback**: Upgrade to Supabase Pro ($25/month) or compress Bronze content.

**4. Retrieval quality insufficient for legal text**
- **Likelihood**: Medium — embedding models may struggle with legal cross-references and defined terms
- **Mitigation**: Phase 9 evaluation with 20-question test set. Tune similarity threshold, consider hybrid search (vector + keyword).
- **Fallback**: Switch to a legal-domain embedding model or add full-text search as a complementary retrieval path.

**5. GitHub Actions minutes budget**
- **Likelihood**: Low if repo is public (unlimited minutes), medium if private (500/month)
- **Mitigation**: Keep scrapers efficient, cache aggressively. Monitor monthly usage.
- **Fallback**: Make repo public (planned anyway for open source).

### Low Risk

**6. Open States API availability**
- **Mitigation**: LegiScan as fallback; Bronze layer caches all retrieved data.

**7. CivicPlus site redesign breaks scrapers**
- **Mitigation**: Change detection alerts when scrapers return zero results. Manual fix required but municipal sites redesign rarely (years, not months).

---

## References

- Design docs: `/docs/high-level-design.md`, `/docs/llds/*.md`
- EARS specs: `/docs/specs/*.md`
- Arrow tracking: `/docs/arrows/index.yaml`
