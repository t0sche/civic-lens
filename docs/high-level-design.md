# High-Level Design: Bel Air Civic Transparency Platform

**Working name:** CivicLens (placeholder — rename freely)
**Scope:** MVP for Bel Air, MD (21015) — State + County + Municipal
**Author:** Stephen Shaffer
**Date:** 2026-03-14
**Status:** DRAFT — awaiting review

---

## 1. Problem Statement

Residents of Bel Air, Maryland are governed by three overlapping layers of government — Maryland state, Harford County, and the Town of Bel Air — each with its own legislative bodies, regulatory processes, and publication systems. There is no unified place for a resident to:

1. **Ask a plain-language question** about what laws apply to them (e.g., "Can I build a fence in my backyard?" requires knowing town zoning code, county regulations, and potentially state environmental law)
2. **Track proposed legislation** across all three layers that could affect their daily life
3. **Understand the status** of bills, ordinances, resolutions, zoning changes, and policy decisions without navigating 6+ separate government websites

The data exists but is fragmented across incompatible systems: two CivicPlus sites (county and town), a custom ASP.NET county bill tracker, eCode360 municipal codes, the Maryland General Assembly site, COMAR regulations, and various PDF archives. No civic tech project currently covers Harford County at any level.

**The core insight:** This is a data integration and accessibility problem, not a data availability problem. The information is public — it's just inaccessible to anyone without hours to spend navigating government websites.

---

## 2. Goals

### Primary Goals (MVP)
- **G1:** Enable plain-language Q&A about laws affecting Bel Air residents across all three government layers via a RAG-powered chat interface
- **G2:** Provide a dashboard showing active/proposed legislation, ordinances, and policy changes at state, county, and municipal levels with status tracking
- **G3:** Minimize ongoing operational cost (target: <$10/month at low traffic) and maintenance burden for a solo maintainer

### Secondary Goals (Post-MVP)
- **G4:** Make the architecture forkable so other jurisdictions can deploy their own instance
- **G5:** Enable freshness monitoring — automated detection when new legislation, agendas, or code changes are published
- **G6:** Support impact analysis — "How would proposed bill X interact with existing county ordinance Y?"

### Success Metrics
- A resident can ask a question about local law and get a sourced, accurate answer within 30 seconds
- The dashboard reflects legislative updates within 24 hours of publication (state) or 48 hours (county/municipal)
- Monthly operating cost stays under $10 at <1,000 monthly users

---

## 3. Target Users and Personas

### Primary: Bel Air Resident
- Homeowner or renter in 21015
- No legal training, no familiarity with government website navigation
- Wants to know: "What are the rules about X?" or "Is anything changing that affects me?"
- Example queries: "What are the noise ordinances?", "Can I run a home business?", "What's being proposed for the Main Street development?"

### Secondary: Engaged Civic Participant
- Attends town meetings occasionally, follows local news
- Wants a single feed of "what's happening" across all government layers
- Cares about proposed changes, not just enacted law
- Example queries: "What bills in Annapolis affect Harford County?", "What's on the Planning Commission agenda next month?"

### Tertiary: Local Journalist / Community Organization
- Needs to track legislative activity systematically
- Values historical context and cross-referencing
- Would use the dashboard more than chat

---

## 4. System Architecture Overview

### 4.1 Architecture Pattern: Medallion Data Pipeline → Dual Interface

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                 │
├────────────┬──────────────┬──────────────┬─────────────────────────┤
│ Open States│ Harford Co.  │ Bel Air      │ eCode360               │
│ / LegiScan │ CivicPlus +  │ CivicPlus +  │ (County + Town Codes)  │
│ APIs       │ Custom Bills │ Legislation  │                         │
│            │ App + PDFs   │ Page + PDFs  │                         │
└─────┬──────┴──────┬───────┴──────┬───────┴────────┬────────────────┘
      │             │              │                │
      ▼             ▼              ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    INGESTION LAYER (Python)                          │
│  GitHub Actions on cron schedule                                    │
│                                                                     │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────────┐  │
│  │ API      │  │ HTML Scraper │  │ PDF       │  │ RSS/Change   │  │
│  │ Clients  │  │ (BS4/Scrapy) │  │ Extractor │  │ Detector     │  │
│  └────┬─────┘  └──────┬───────┘  └─────┬─────┘  └──────┬───────┘  │
│       │               │                │               │           │
│       └───────────────┴────────────────┴───────────────┘           │
│                              │                                      │
└──────────────────────────────┼──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA LAYER (Supabase)                             │
│                                                                     │
│  ┌──────────────────┐  ┌────────────────┐  ┌────────────────────┐  │
│  │ BRONZE           │  │ SILVER         │  │ GOLD               │  │
│  │ Raw documents,   │  │ Normalized     │  │ Embeddings         │  │
│  │ HTML snapshots,  │  │ legislative    │  │ (pgvector),        │  │
│  │ PDF text         │  │ items with     │  │ dashboard-ready    │  │
│  │                  │  │ metadata,      │  │ materialized       │  │
│  │                  │  │ jurisdiction,  │  │ views              │  │
│  │                  │  │ status, dates  │  │                    │  │
│  └──────────────────┘  └────────────────┘  └────────────────────┘  │
│                                                                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
┌──────────────────────────┐  ┌──────────────────────────────────────┐
│     CHAT INTERFACE       │  │        DASHBOARD                     │
│                          │  │                                      │
│  Query → pgvector        │  │  Legislative tracker (state/county/  │
│  retrieval → model       │  │  municipal), status filters,         │
│  routing → response      │  │  jurisdiction drill-down,            │
│  with citations          │  │  upcoming meetings, recent changes   │
│                          │  │                                      │
│  Free model (simple) ──┐ │  │  Server-rendered from Silver/Gold   │
│  Claude API (complex)──┘ │  │  tables                              │
└──────────────────────────┘  └──────────────────────────────────────┘
│                                                                     │
│                    FRONTEND (Next.js on Vercel)                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Component Summary

| Component | Technology | Why This Choice |
|-----------|-----------|-----------------|
| **Ingestion** | Python scripts via GitHub Actions (cron) | Your comfort zone; no always-on compute cost; git-tracked scraper changes |
| **Database** | Supabase (Postgres + pgvector) | Free tier (500MB DB, 1GB storage); pgvector for embeddings; managed infrastructure |
| **Frontend** | Next.js on Vercel free tier | SSR dashboard + API routes for chat in one deploy; zero server management |
| **Embeddings** | Gemini embedding API (free tier) or `all-MiniLM-L6-v2` in GitHub Action | Zero cost; sufficient quality for legal text retrieval |
| **Chat — simple queries** | Gemini 2.5 Flash (free tier) | Zero cost for direct-answer questions where context is in a single chunk |
| **Chat — complex queries** | Claude API (Sonnet) | Multi-document synthesis, cross-jurisdictional reasoning, impact analysis |
| **Model router** | Heuristic classifier in API route | Keyword/intent based: multi-jurisdiction or "how does X affect Y" → Claude; everything else → free model |

### 4.3 Data Source → Collection Strategy Mapping

Based on the data audit, each source maps to a specific collection tier. Sources are phased by implementation priority (Phase 9 = next, Phase 10–11 = deferred).

**Federal APIs — Free structured federal data (Phase 9–10)**
| Source | Endpoint | Auth | Phase | Notes |
|--------|----------|------|-------|-------|
| Congress.gov API | `api.congress.gov` | Free api.data.gov key | 9 | Replaces defunct ProPublica Congress API (shut down Feb 4, 2025). MD-01 covers Harford County. |
| GovInfo API | `api.govinfo.gov` | Free api.data.gov key | 9 | Full text of bills, Federal Register, CFR, Congressional Record. |
| USA Spending API | `api.usaspending.gov` | None | 9 | Federal contracts/grants. Filter by Harford County FIPS 24025. Aberdeen Proving Ground (APG) makes this unusually relevant — large DoD contracts. |
| Census / ACS API | `api.census.gov` | Free key | 10 | Population, income, home value, poverty for FIPS 24025. |
| FEMA NFHL | ArcGIS REST | None | 10 | National Flood Hazard Layer by county. Flood zones, base flood elevations. |
| EPA ECHO | `echo.epa.gov/tools/web-services/` | None | 10 | Facility enforcement and compliance data by county/ZIP. Updated weekly. |
| BLS LAUS | `api.bls.gov/publicAPI/v2/` | Free key | 10 | Harford County unemployment series `LAUCN240250000000003`. |
| HUD Fair Market Rents | `huduser.gov/hudapi/public/fmr/` | Free token | 10 | FMR for ZIP 21015. 2025 two-bedroom: $1,965/month. |
| OpenFEC | `api.open.fec.gov` | Free api.data.gov key | 10 | Campaign finance for MD-01, MD Senate races. |

**State APIs — Tier 1 structured (Phase 9)**
| Source | API | Data Available | Update Cadence |
|--------|-----|----------------|----------------|
| Open States | REST v3 (JSON) | MD bills, votes, sponsors, committees | Multiple times/day |
| LegiScan | REST (JSON/CSV) | MD bills, full text, status, votes | Daily + weekly bulk |
| MGA Bulk CSV/JSON | `mgaleg.maryland.gov/mgawebsite/Legislation/OpenData` | All bill metadata since 2013, 79 subject categories | Throughout session |
| MD Open Data Portal | SODA REST | 1,000+ contextual datasets | Varies |

**Local GIS — ArcGIS REST (Phase 9)**
| Source | Hub | Data Available | Notes |
|--------|-----|----------------|-------|
| Harford County ArcGIS Hub | `harford-county-gis-hub-harfordgis.hub.arcgis.com` | Parcels, zoning, land use, floodplains, wetlands, road centerlines | Not federated into MD Open Data Portal |
| Bel Air ArcGIS Hub | `toba-data-hub-belairmd.hub.arcgis.com` | Zoning, property boundaries, parks, infrastructure | Newly discovered; REST API access |

**Tier 2 — Structured scraping (Phase 9)**
| Source | Method | Data Available | Fragility |
|--------|--------|----------------|-----------|
| Bel Air legislation page | HTML parse (BS4) | Ordinances/resolutions 2018+ with status | Low — simple HTML table |
| CivicPlus RSS feeds (11 boards) | RSS polling | 11 Bel Air board/commission feeds + Alert Center, Calendar, News Flash, Jobs; Harford County RSS | Low — standard RSS |
| CivicPlus AgendaCenter (both) | RSS + HTML parse | Agendas for 60+ county boards, 12 town boards | Low-Medium — stable CMS |
| eCode360 (county + town codes) | HTML scrape or PDF (`.extra/`) | Full codified law, hierarchical | Low — well-structured HTML. PDF available in `.extra/` for initial load without live scraping. |
| Harford Co. custom bills app | HTTP requests + HTML parse | County council bills/resolutions | Medium — custom ASP.NET app |
| Harford Co. ZBA | HTTP + HTML parse (extends harford_bills.py) | ZBA cases, variances, hearings, decisions | Low — same ASP.NET codebase |

**Tier 2 — Structured scraping (Phase 10+)**
| Source | Method | Data Available | Fragility |
|--------|--------|----------------|-----------|
| Bel Air DocumentCenter | Sequential numeric ID crawl | Budgets FY2012–2026, audits, capital plans, minutes archives | Low — sequential IDs |
| MD Judiciary RSS | RSS polling | Appellate opinions, judicial news | Low — standard RSS |
| Swagit/Granicus video archives | HTML parse | County meeting recordings back to 2011 with linked agendas | Medium — HTML structure |
| Harford Development Review Dashboard | ArcGIS Feature Service | Active concept plans, site plans, community input | Medium — ArcGIS feature service |

**Tier 3 — PDF extraction (ongoing effort)**
| Source | Method | Data Available | Fragility |
|--------|--------|----------------|-----------|
| Council/Commissioner meeting minutes | pdfplumber + LLM extraction | Decisions, votes, discussion summaries | Medium — PDF quality varies |
| Fiscal notes, staff reports | pdfplumber | Budget impacts, analysis | Medium |
| MGA Bill text | pdfplumber (predictable PDF URL pattern) | Full bill text for MD General Assembly | Low — stable URL pattern |
| Harford Co. Laserfiche docs | Headless browser + PDF extraction | Historical council documents | High — session-based navigation |
| COMAR regulations | Headless browser (SharePoint) | State regulations (legal constraints on reuse) | High — JS-heavy, legal risk |

**Deprecated Sources**
| Source | Status | Replacement |
|--------|--------|-------------|
| ProPublica Congress API | **DEFUNCT** (GitHub archived Feb 4, 2025) | Congress.gov API (ingestion-federal arrow) |
| Google Civic Information — Representatives | **DEFUNCT** (April 30, 2025) | Cicero API (commercial) or OCD-ID lookups |
| Regulations.gov POST API | **Restricted** (Aug 2025) | GET endpoints still functional |

**Strategic Gaps**
- **Maryland campaign finance (MD CRIS)** — 17 years of contribution data behind HTML-only search at `campaignfinance.maryland.gov`. No API, no bulk download.
- **Harford County non-federation** — Harford County is NOT federated into `opendata.maryland.gov`. County-level structured data limited to GIS layers.
- **Public safety data** — Harford County Sheriff's Office does not publish structured crime statistics.

---

## 5. Key Design Decisions and Trade-offs

### D1: Open States/LegiScan over direct MGA scraping
**Decision:** Use third-party APIs for state legislative data instead of scraping mgaleg.maryland.gov.
**Rationale:** MGA has no API, uses ASP.NET forms with session state, and would require significant scraper maintenance. Open States and LegiScan provide structured JSON with better reliability.
**Trade-off:** Slight data latency (hours, not minutes) vs. dramatically lower maintenance. Dependency on third-party API availability.
**Risk:** Open States funding/availability. Mitigated by LegiScan as fallback + local caching of all retrieved data.

### D2: Supabase over self-hosted Postgres
**Decision:** Use Supabase managed Postgres with pgvector extension.
**Rationale:** Free tier is sufficient for MVP scale. Eliminates database operations burden. Built-in auth if user accounts are ever needed. pgvector avoids a separate vector store (Pinecone, Weaviate).
**Trade-off:** 500MB storage limit on free tier may require moving to paid ($25/mo) as document corpus grows. Vendor lock-in on Supabase-specific features (auth, realtime).
**Risk:** Outgrowing free tier. Mitigated by medallion architecture — Bronze layer can be stored in cheaper object storage (Supabase Storage or S3) with only Silver/Gold in Postgres.

### D3: Heuristic model routing over cascade or user-triggered
**Decision:** Route queries to free vs. frontier models using keyword/intent heuristics, not user toggles or confidence cascading.
**Rationale:** Users don't know which model they need. Cascade adds latency and complexity. Heuristics are predictable, debuggable, and sufficient for the query patterns in this domain.
**Trade-off:** Some queries will be misrouted (complex question sent to free model, simple question sent to Claude). Acceptable at MVP — can refine heuristics with usage data.
**Routing logic (initial):**
- → **Claude API** if query: references multiple jurisdictions, asks "how does X affect Y", requests impact analysis, or retrieval returns chunks from 3+ documents
- → **Free model** for: single-document Q&A, definition lookups, "what is the law on X", meeting schedule questions

### D4: Section-aware chunking over naive text splitting
**Decision:** Chunk legal documents by section/subsection boundaries, not by token count.
**Rationale:** Legal text has deeply nested cross-references ("as defined in §4-201(b)(3)") that lose meaning when split mid-section. Section boundaries are natural semantic units in codified law.
**Trade-off:** Uneven chunk sizes (some sections are 50 tokens, others are 2,000). Requires source-specific parsing logic for each document format (eCode360 HTML sections, PDF section headers, bill text articles).
**Risk:** Some sections may be too long for embedding quality. Mitigated by sub-chunking large sections with overlap while preserving parent section metadata.

### D5: GitHub Actions for ingestion over dedicated scheduler
**Decision:** Run all scraping/ingestion as scheduled GitHub Actions workflows.
**Rationale:** Free for public repos (2,000 minutes/month); scraping runs are short (< 5 minutes each); git-tracked changes to scraper logic; built-in failure notifications; no infrastructure to manage.
**Trade-off:** 6-hour minimum cron granularity (fine for legislative data). Can't react to real-time events — but CivicPlus RSS polling every 6 hours is more than sufficient for municipal legislation cadence.
**Risk:** GitHub Actions minutes exhaustion if scraping becomes complex. Mitigated by keeping scrapers efficient and caching aggressively.

### D6: eCode360 HTML scraping over paid API (initially)
**Decision:** Scrape the free eCode360 HTML for both county and town codes rather than paying for API access ($250 setup + $595/year per municipality).
**Rationale:** The HTML is well-structured with hierarchical navigation and permanent section URLs. Paid API is an optimization, not a requirement.
**Trade-off:** Scraping is more fragile than API access. If eCode360 changes their HTML structure, scrapers break.
**Risk:** Low — eCode360's HTML has been stable for years. Revisit if scraper maintenance becomes burdensome or if the project gets funding.

### D7: COMAR deferred to post-MVP
**Decision:** Exclude COMAR (Code of Maryland Regulations) from the MVP data corpus.
**Rationale:** Three compounding problems: (1) SharePoint-based site requires JavaScript rendering, (2) content is served one regulation at a time with no bulk access, (3) Maryland law (State Government Article §7-206.2) restricts reuse to personal use only, creating legal risk for a published application. State *bills* (via Open States/LegiScan) are sufficient for MVP.
**Trade-off:** Residents asking about state regulations (as opposed to statutes) will get incomplete answers. The chat should explicitly disclaim this gap.
**Revisit when:** Legal counsel can assess the personal-use restriction, or Maryland publishes an open data version of COMAR.

---

## 6. Non-Goals (Explicitly Out of Scope for MVP)

- **NG1: Federal law.** Federal legislation affecting the area is excluded from MVP. The complexity of mapping federal law to local impact is a separate project.
- **NG2: COMAR / state regulations.** Per D7 above — legal and technical barriers.
- **NG3: Real-time updates.** 6-24 hour refresh cadence is acceptable. No websockets, no push notifications.
- **NG4: User accounts or personalization.** No login, no saved searches, no "my watchlist." Anonymous public access only.
- **NG5: Legal advice.** The system provides information about what laws exist and their status. It does not interpret legal meaning or provide recommendations. Every response must include a disclaimer.
- **NG6: Historical analysis.** MVP tracks *current* law and *active* proposed changes. Historical bill tracking and trend analysis are post-MVP.
- **NG7: Meeting transcription.** YouTube auto-captions provide metadata, but full meeting transcription/summarization is post-MVP.
- **NG8: Multi-jurisdiction generalization.** The architecture should be *forkable* but the MVP is hardcoded for Bel Air/Harford County/Maryland. Abstraction into a configurable framework is post-MVP.

---

## 7. Data Model (Conceptual)

### Silver Layer: Normalized Legislative Item

Every piece of tracked legislation/regulation, regardless of source, normalizes to a common schema:

```
legislative_item:
  id:              UUID
  source_id:       string        # Original ID from source system (bill number, ordinance number, etc.)
  jurisdiction:    enum           # STATE | COUNTY | MUNICIPAL
  body:            string        # "Maryland General Assembly" | "Harford County Council" | "Bel Air Board of Commissioners" | etc.
  item_type:       enum           # BILL | ORDINANCE | RESOLUTION | EXECUTIVE_ORDER | ZONING_CHANGE | POLICY | AGENDA_ITEM
  title:           string
  summary:         text           # LLM-generated plain-language summary
  status:          enum           # INTRODUCED | IN_COMMITTEE | PASSED_ONE_CHAMBER | ENACTED | VETOED | EXPIRED | PENDING | TABLED | REJECTED | APPROVED
  introduced_date: date
  last_action_date: date
  last_action:     string        # Human-readable last action description
  sponsors:        string[]
  source_url:      string        # Canonical URL to source document
  tags:            string[]       # LLM-generated topic tags for filtering
  full_text_ref:   string        # Reference to Bronze layer raw document
  created_at:      timestamp
  updated_at:      timestamp
```

### Silver Layer: Code Section

```
code_section:
  id:              UUID
  jurisdiction:    enum           # COUNTY | MUNICIPAL
  code_source:     string        # "Harford County Code" | "Town of Bel Air Code"
  chapter:         string        # e.g., "Chapter 165 - Development Regulations"
  section:         string        # e.g., "§165-23 Fences and walls"
  title:           string
  content:         text           # Full section text
  parent_section:  UUID?          # Hierarchical reference
  source_url:      string
  effective_date:  date?
  last_amended:    date?
  created_at:      timestamp
  updated_at:      timestamp
```

### Gold Layer: Embeddings

```
document_chunk:
  id:              UUID
  source_type:     enum           # LEGISLATIVE_ITEM | CODE_SECTION | MEETING_MINUTES | OTHER
  source_id:       UUID           # FK to Silver layer record
  jurisdiction:    enum
  chunk_text:      text
  chunk_index:     integer        # Position within source document
  section_path:    string         # Hierarchical breadcrumb (e.g., "Town Code > Ch. 165 > §165-23")
  embedding:       vector(384)    # Or vector(768) depending on model
  metadata:        jsonb          # Flexible metadata for retrieval filtering
  created_at:      timestamp
```

---

## 8. Phased Delivery Plan (Overview)

Detailed implementation plan will be in `/docs/planning/`, but the high-level phases:

### Phase 1: Data Foundation (Weeks 1-2)
- Stand up Supabase with Bronze/Silver/Gold schemas
- Implement Tier 1 API clients (Open States, LegiScan)
- Implement eCode360 HTML scraper for town code
- Populate Silver layer with state bills + town code sections
- Generate embeddings, verify retrieval quality
- **Milestone:** Can query town code via SQL; state bills are normalized and searchable

### Phase 2: Chat MVP (Weeks 3-4)
- Next.js app with chat interface
- RAG pipeline: query → pgvector retrieval → prompt construction → model response
- Model routing heuristic (free vs. Claude API)
- Citation linking back to source documents
- Legal disclaimer on every response
- **Milestone:** A resident can ask "What are the fence regulations in Bel Air?" and get a sourced answer

### Phase 3: Dashboard MVP (Weeks 5-6)
- Legislative tracker view: filterable by jurisdiction, status, type, date
- Active/pending items highlighted
- Upcoming meetings calendar (scraped from CivicPlus)
- Basic search and topic filtering
- **Milestone:** Dashboard shows all active state bills + county/town legislation with status

### Phase 4: County + Expansion (Weeks 7-8)
- Harford County custom bills app scraper
- County CivicPlus AgendaCenter scraper
- County code (eCode360) ingestion
- PDF extraction pipeline for meeting minutes
- RSS-based change detection
- GitHub Actions cron scheduling for all scrapers
- **Milestone:** All three jurisdiction layers populated and refreshing automatically

### Phase 5: Hardening (Weeks 9-10)
- Scraper failure alerting
- Stale data detection and user-facing freshness indicators
- Response quality evaluation (manual spot-checking + automated retrieval metrics)
- Cost monitoring and model routing optimization
- README and deployment docs for forkability
- **Milestone:** System runs unattended for 2 weeks with acceptable data freshness

---

## 9. Open Questions

- **OQ1:** Should the chat include a confidence indicator? ("I'm fairly confident about this" vs. "This answer draws from multiple sources and may be incomplete")
- **OQ2:** How to handle conflicting information across jurisdictions? (State law preempts local ordinance — should the system attempt to reason about preemption?)
- **OQ3:** Is the eCode360 HTML scraping approach legally permissible for a published application, or do we need to negotiate API access?
- **OQ4:** Should meeting agenda items from CivicPlus be normalized into the same `legislative_item` schema, or do they warrant a separate schema?
- **OQ5:** What's the right embedding model? `all-MiniLM-L6-v2` (384 dims, fast, free) vs. Gemini embedding (768 dims, free tier, better quality) vs. a legal-domain-specific model?
- **OQ6:** Project name — "CivicLens" is a placeholder. What do you want to call this?
