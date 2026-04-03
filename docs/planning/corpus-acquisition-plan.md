# CivicLens Corpus Acquisition Plan
**Date:** 2026-03-26
**Status:** Active — implementation in progress
**Scope:** Harford County + Town of Bel Air PDF corpus for RAG pipeline

---

## 1. Immediate Actions — Manual Downloads (Priority List)

The following 10 documents should be manually downloaded first. All URLs were confirmed accessible via web search and Google index cache. Download these PDFs to `corpus/` subdirectories as specified and add the JSON sidecar described in §2.

### Top 10 Priority Documents

| # | Document | URL | Local Path | Jurisdiction | Doc Type |
|---|----------|-----|------------|--------------|---------|
| 1 | Harford County FY26 Approved Operating Budget | `https://www.harfordcountymd.gov/3864/Approved-FY26-Budget` (navigate to full operating budget PDF) | `corpus/harford/fy2026-operating-budget.pdf` | COUNTY | budget |
| 2 | Harford County ACFR FY2024 | `https://www.harfordcountymd.gov/DocumentCenter/View/26925/June-30-2024-ACFR-PDF` | `corpus/harford/acfr-fy2024.pdf` | COUNTY | financial_report |
| 3 | Bel Air FY26 Final Budget (Resolution 1252-25) | `https://belairmd.org/DocumentCenter/View/6958/RES-1252-25-FY26-Final-Budget-Binder1` | `corpus/belair/fy2026-final-budget.pdf` | MUNICIPAL | budget |
| 4 | Harford County Zoning Code (current) | `https://www.harfordcountymd.gov/DocumentCenter/View/2257/Zoning-Code-PDF` | `corpus/harford/zoning-code-current.pdf` | COUNTY | zoning |
| 5 | Harford County Subdivision Regulations (current) | `https://www.harfordcountymd.gov/DocumentCenter/View/2256/Subdivision-Regulations-PDF` | `corpus/harford/subdivision-regulations-current.pdf` | COUNTY | regulation |
| 6 | Bel Air Comprehensive Plan 2022 | `https://belairmd.org/DocumentCenter/View/92/Comprehensive-Plan-Book` | `corpus/belair/comprehensive-plan-2022.pdf` | MUNICIPAL | comprehensive_plan |
| 7 | Bel Air Police Department Annual Report 2023 | `https://www.belairmd.org/DocumentCenter/View/6950/2023` | `corpus/belair/police-annual-report-2023.pdf` | MUNICIPAL | annual_report |
| 8 | Harford County FY25 Budget Message | `https://www.harfordcountymd.gov/DocumentCenter/View/25925/FY2025-Budget-Message-from-Harford-County-Executive-Bob-Cassilly` | `corpus/harford/fy2025-budget-message.pdf` | COUNTY | budget |
| 9 | Bel Air Zoning Quick Reference Guide | `https://www.belairmd.org/DocumentCenter/View/1328/QUICK-REFERENCE-GUIDE-FOR-ZONING-DISTRICTS` | `corpus/belair/zoning-quick-reference.pdf` | MUNICIPAL | zoning |
| 10 | Harford County FY22 Proposed Operating Budget (structural baseline) | `https://www.harfordcountymd.gov/DocumentCenter/View/18047/Harford-County-FY22-Proposed-Operating-Budget` | `corpus/harford/fy2022-proposed-operating-budget.pdf` | COUNTY | budget |

**Prioritization rationale:**
- Items 1–3: Budget documents are the single most common resident query ("What is the property tax rate?", "How much does the town spend on police?")
- Items 4–5: Zoning/subdivision questions are the second most common local government query
- Items 6–7: Comprehensive plan and police report answer "Where is Bel Air headed?" and public safety questions
- Items 8–10: Historical budget context + secondary zoning reference

**Note on Harford FY26 budget:** The approved FY26 budget page is at `harfordcountymd.gov/3864/Approved-FY26-Budget`. The page links to at minimum three PDFs: Budget-in-Brief, Operating Budget, and Capital Budget. Download all three and name them `-brief`, `-operating`, and `-capital` suffixed. The full operating budget is the highest priority.

---

## 2. Manual Ingest Pipeline Spec

### 2.1 Folder Structure

```
corpus/
  harford/          # Harford County documents
    *.pdf
    *.json          # sidecar metadata (one per PDF)
  belair/           # Town of Bel Air documents
    *.pdf
    *.json
  state/            # Maryland state documents (future)
    *.pdf
    *.json
```

### 2.2 Metadata Sidecar Schema

Each PDF `{stem}.pdf` must have a matching `{stem}.json` sidecar. Alternatively the filename convention (§2.3) provides fallback defaults for most fields.

**Full sidecar schema (`{stem}.json`):**

```json
{
  "jurisdiction": "COUNTY",          // required: "COUNTY" | "MUNICIPAL" | "STATE"
  "doc_type": "budget",              // required: see doc_type vocabulary below
  "date": "2025-06-01",             // required: ISO 8601 date (publication or effective date)
  "source_url": "https://...",       // required: canonical URL the PDF was downloaded from
  "title": "FY2026 Approved Operating Budget",  // optional: human title (falls back to filename)
  "fiscal_year": "FY2026",           // optional: for budget/financial docs
  "body": "Office of Budget & Management",      // optional: issuing body
  "notes": "Pages 1-412 only; appendices omitted"  // optional: free text
}
```

**Doc type vocabulary:**
`budget` | `financial_report` | `zoning` | `regulation` | `comprehensive_plan` | `annual_report` | `ordinance` | `resolution` | `minutes` | `agenda` | `policy` | `other`

**Validation rules:**
- `jurisdiction` must be one of the three string literals
- `date` must parse as ISO 8601 (YYYY-MM-DD or YYYY-MM)
- `source_url` must be a valid http(s) URL
- All other fields are optional with sensible defaults derived from filename/path

### 2.3 Filename Convention Fallback

When no sidecar is found, the ingester derives metadata from the filename using the pattern:

```
{jurisdiction_prefix}-{doc_type}-{YYYY}-{slug}.pdf
```

Examples:
- `harford-budget-2026-operating.pdf` → jurisdiction=COUNTY, doc_type=budget, date=2026
- `belair-zoning-2022-comprehensive-plan.pdf` → jurisdiction=MUNICIPAL, doc_type=zoning, date=2022
- `harford-financial_report-2024-acfr.pdf` → jurisdiction=COUNTY, doc_type=financial_report, date=2024

Jurisdiction prefix mapping: `harford` → COUNTY, `belair` → MUNICIPAL, `state` / `md` → STATE

### 2.4 CLI Interface

```bash
# Ingest all PDFs in a directory
python -m src.ingestion.manual_ingest --dir corpus/harford/

# Ingest a single PDF with explicit sidecar
python -m src.ingestion.manual_ingest --dir corpus/belair/ --file belair-budget-2026-final.pdf

# Dry run (validate metadata, skip Bronze write)
python -m src.ingestion.manual_ingest --dir corpus/harford/ --dry-run

# Ingest all corpus subdirectories
python -m src.ingestion.manual_ingest --dir corpus/
```

### 2.5 Bronze Layer Mapping

| Sidecar Field | `upsert_bronze_document()` Param | Notes |
|--------------|----------------------------------|-------|
| (filename stem + dir) | `source_id` | e.g., `manual:harford/fy2026-operating-budget` |
| `"manual_pdf"` (constant) | `source` | Distinguishes from automated scrapers |
| `doc_type` | `document_type` | Passed through directly |
| extracted text (pdfplumber) | `raw_content` | Full page text, pages joined with `\n\n---\n\n` |
| all sidecar fields | `raw_metadata` | Passed as dict |
| `source_url` | `url` | |

`source_id` format: `manual:{subdir}/{stem}` — e.g., `manual:harford/fy2026-operating-budget`. This ensures manual ingests are namespaced separately from automated scrapers and are idempotent (re-running on the same PDF is a no-op if content unchanged).

---

## 3. DocumentCenter Crawler Plan (Bel Air)

### 3.1 ID Range Research

From Google index analysis of `belairmd.org/DocumentCenter/View/{ID}`:
- **Lowest confirmed IDs:** ~92 (Comprehensive Plan Book), ~309 (Sign Application), ~514-515 (permit forms)
- **Highest confirmed ID:** ~7319 (2026 RFP document), with budget/finance docs in the 6000s-7000s range
- **Estimated active range:** 1 – 7500 (with significant gaps; many IDs likely return 404 or redirect)

The IDs are sequential across all document categories (not per-category). Google search found IDs from 92 to 7319 as publicly indexed, suggesting the current max is somewhere in the 7300-7500 range.

### 3.2 Index-First Strategy

**Do not download PDFs speculatively.** Instead:

1. Enumerate IDs in batches of 50, fetching only the HTML metadata page (`/DocumentCenter/View/{ID}/`)
2. Parse the title, category, and upload date from the page `<title>` and `<h1>` tags
3. Write a CSV index (`corpus/belair_docenter_index.csv`) with columns: `id, title, category, url, date, size_hint`
4. Human reviews CSV and flags rows for download (adds `download=true` column)
5. Second pass downloads flagged PDFs and places them in `corpus/belair/`

### 3.3 Proposed Lightweight Crawler

**Implementation:** `src/ingestion/scrapers/belair_docenter_crawler.py`

Key design decisions:
- Uses `requests` only (no headless browser needed — metadata page is server-side HTML)
- Configurable `--start-id`, `--end-id`, `--batch-size` (default 50), `--delay` (default 1.0s)
- On HTTP 200: parse `<title>` tag (format: `{Document Title} | Town of Bel Air, MD`), extract category from breadcrumb or URL
- On HTTP 404 / redirect to root: record as `not_found`, skip
- On HTTP 403 / 429: back off and log warning
- Writes/appends to CSV index after each batch

**Response pattern expected:**
- HTTP 200 with HTML: document exists, parse metadata
- HTTP 302 redirect to `/DocumentCenter/Home`: document does not exist or is private
- HTTP 403: rate-limited or bot-blocked (unlikely for metadata-only requests)

**Target categories to prioritize in human review:**
- Budgets (FY2012–FY2026 annual budgets)
- Audits / ACFRs (2015–2024)
- Capital Improvement Plans
- BOA (Board of Appeals) meeting minutes
- Planning Commission minutes
- Historic Preservation Commission minutes
- Resolutions and Ordinances (complements `belair_legislation.py` scraper)

### 3.4 robots.txt Status

`belairmd.org/robots.txt` returned HTTP 403 during research (same as all direct fetches from this IP range). However:
- The site is publicly accessible from browsers (CivicPlus does not block all bots)
- The 403 responses to `WebFetch` suggest Cloudflare-style bot detection or IP-based blocking
- CivicPlus sites are generally crawlable with browser-like headers (User-Agent, Accept, Referer)
- The crawler should use the same polite `User-Agent` string used in `harford_bills.py`

**Recommendation:** Send `Referer: https://www.belairmd.org/DocumentCenter` and `Accept: text/html` headers. Add a 1.0s delay between requests. This matches the behavior of a human clicking through the site and is unlikely to trigger rate limits.

---

## 4. CivicPlus AgendaCenter Fix

### 4.1 Current Status

`civicplus_agenda.py` is a stub (Phase 8+ deferred). The file notes that "AgendaCenter uses JavaScript for year selection dropdown, requiring a headless browser (Playwright) for full historical access."

### 4.2 Diagnosis

**What the year dropdown actually does:**
The CivicPlus AgendaCenter year dropdown is a `<select>` element that triggers a page reload (not an AJAX call) via a standard HTML form `GET` request. The year is passed as a query parameter:

```
https://belairmd.org/AgendaCenter?catID={N}&year={YYYY}
```

This means **Playwright is NOT required** for current-year or known-year access. The dropdown only requires JavaScript if you want to discover the list of available years dynamically. Since we know the year range (2014–2026 at minimum), we can enumerate years directly.

**Confirmed URL patterns (from search results):**
- Agendas: `/AgendaCenter/ViewFile/Agenda/_MMDDYYYY-{id}` — direct PDF, no auth required
- Minutes: `/AgendaCenter/ViewFile/Minutes/_MMDDYYYY-{id}` — direct PDF, no auth required
- ID range for minutes: ~420 (2019) → ~1088 (Nov 2025), incrementing sequentially

**Why current requests-based scraping may fail:**
1. The main `AgendaCenter` index page uses JavaScript to render the meeting list — `requests` will get a mostly-empty page with a `<div id="agendacenter">` placeholder
2. However, the `/ViewFile/` PDF endpoints are **direct downloads** — no JavaScript needed
3. The failure is at the discovery step, not the download step

### 4.3 Recommended Fix

**Two-phase approach (no Playwright required for recent documents):**

**Phase A — RSS-based discovery (implement first, lowest effort):**
The CivicPlus RSS feed at `belairmd.org/rss.aspx` provides meeting agenda links without JavaScript. Pattern:
```
https://www.belairmd.org/RSSFeed.aspx?ModID=820&CID=AgendaCenter
```
RSS items contain the `ViewFile` URL and meeting metadata. This covers new documents going forward.

**Phase B — ID enumeration for historical discovery (medium effort):**
The `/AgendaCenter/ViewFile/Minutes/_MMDDYYYY-{id}` IDs are sequential. Based on observed data:
- 2019: IDs ~420
- 2020: IDs ~461
- 2023: IDs ~787
- 2024: IDs ~890–938
- 2025: IDs ~987–1088

Enumerate IDs 400–1200 with a HEAD request. On HTTP 200, queue for full download. On HTTP 404, skip.

**Specific code change needed in `civicplus_agenda.py`:**

Replace the current stub with an implementation that:
1. Polls the RSS feed for new agendas/minutes (`feedparser` is already in `requirements.txt`)
2. Extracts `ViewFile` URLs from RSS `<link>` elements
3. Downloads PDFs via `requests.get()` with `Referer: https://www.belairmd.org/AgendaCenter` header
4. Hands off to `pdf_extractor.extract_text_from_pdf()` once that module is implemented
5. Writes to Bronze layer via `upsert_bronze_document()` with `source="civicplus_agenda"`, `document_type="agenda"` or `"minutes"`

**No Playwright needed** for the RSS-first strategy. Playwright should be reserved for historical batch enumeration only (Phase 10+).

---

## 5. Laserfiche Assessment (Harford County)

### 5.1 Portal Details

**URL:** `http://hcgweb01.harfordcountymd.gov/WebLink/`
**Version:** Laserfiche WebLink 9 (© 1998–2015 Laserfiche)
**Authentication:** Public access available (no login required for public documents)

### 5.2 What's Available

Based on search results, the Harford County Laserfiche WebLink hosts:
- All past and current **County Council bills and resolutions** (the Council Library)
- **Council agendas and minutes** (legislative history)
- **Planning & Zoning** records including subdivision plans
- Historical documents back to at least **1981** (document IDs in the 4000s range found for 1981)

Direct document URL pattern: `http://hcgweb01.harfordcountymd.gov/WebLink/0/doc/{docID}/Page1.aspx`
Folder browse URL pattern: `http://hcgweb01.harfordcountymd.gov/WebLink/0/fol/{folderID}/Row1.aspx`

### 5.3 Feasibility Assessment

**Verdict: Feasible but lower priority than manual downloads + DocumentCenter crawl.**

**Arguments for automation:**
- Public access (no authentication) — confirmed via search result links
- Standard WebLink 9 HTML structure — predictable with BeautifulSoup
- Contains council legislative history that complements `harford_bills.py` metadata
- Folder IDs and document IDs are numeric and enumerable

**Arguments against (for now):**
- WebLink 9 returns HTTP 403 to automated fetch tools (confirmed during research — same 403 pattern as `harfordcountymd.gov`)
- WebLink 9 has no public REST API — the Laserfiche REST API requires a self-hosted API server that Harford County has not publicly exposed
- The `harford_bills.py` scraper already gets bill metadata from the separate ASP.NET app; Laserfiche would add bill text PDFs only
- Bill text PDFs are available through the `harfordcountymd.gov/DocumentCenter/` path for recent bills (higher quality, CivicEngage-hosted)
- Session management is required even for "public" WebLink access (cookie-based)

**Conclusion:** Do not automate Laserfiche WebLink in Phase 9/10. The bill text and legislative history overlap significantly with what `harford_bills.py` already captures as metadata. The manual download pipeline (§2) handles the high-value non-bill documents. Revisit in Phase 11 if the Council Library's pre-2018 bill texts become a user need.

**If automation is ever implemented:**
- Use `requests.Session()` with cookie persistence — WebLink requires a session cookie from the landing page
- Do NOT use Playwright unless the session cookie approach fails (adds ~300ms/page overhead)
- Begin with folder browse at known Council Library folder ID (discovered via `harfordcountymd.gov/1257/Council-Library` link)
- Rate limit to 2 requests/second to avoid triggering rate limiting

---

## 6. Defer List

The following sources are explicitly deferred from corpus acquisition work, with rationale:

| Source | Reason to Defer |
|--------|----------------|
| Harford County permit monthly reports (`harfordcountymd.gov/2163/Data-Reports`) | Tabular data (permit counts) — low RAG relevance vs. effort; no narrative text for Q&A |
| Maryland Transparency Portal (`mtp.maryland.gov`) | Socrata dashboards not PDF-based; covered by future structured API integration |
| Maryland Case Search | Web-only, no API, launched March 14, 2026 — too new and too broad |
| MD Land Records (`mdlandrec.net`) | Requires registration; deeds/mortgages are property-specific, not civic policy |
| Historical Harford Council bills via Laserfiche (pre-2018) | Covered by `harford_bills.py` metadata; full text adds marginal RAG value |
| Harford County ePermit Center (EnerGov) | No documented REST API; individual permits are too granular for RAG corpus |
| Bel Air Police reports pre-2023 | Reports from 2016–2022 exist but crime statistics are low-query-relevance |
| HCPS Board of Education budget | Separate institution; out of scope for Town/County focus of Phase 9 |
| Swagit/Granicus video archives | Video transcription pipeline not in scope; deferred to Phase 11+ |

---

## 7. Integration Notes

All paths in this plan integrate with the existing Bronze layer without redesign:

- `manual_ingest.py` calls `upsert_bronze_document()` directly (same as all other scrapers)
- PDF text extracted by `pdfplumber` becomes `raw_content` (the same field used by JSON scrapers)
- `source="manual_pdf"` namespaces manual ingests cleanly from automated sources
- The DocumentCenter crawler produces a CSV index for human review, then feeds back through `manual_ingest.py` for actual ingestion (not a separate write path)
- CivicPlus AgendaCenter RSS fix uses `feedparser` (already in `requirements.txt`) and the existing `upsert_bronze_document()` contract

No schema changes to `bronze_documents` are needed. The `raw_metadata` JSONB column is sufficient to store all PDF-specific metadata (jurisdiction, doc_type, fiscal_year, source_url, page_count).
