# Plan: Zip-Code Configurable CivicLens + Stats Page

## Context

CivicLens has 72 hardcoded references to "Bel Air", "Maryland", "Harford County", and "21015" across 13+ files. A user forking the repo to deploy for their own locality would need to hunt through every file. The goal is: **change one config file, re-deploy, done.**

Additionally, users need a `/stats` page showing jurisdiction coverage, data freshness, and pipeline health.

---

## Part 1: Central Config — `civic-lens.config.json`

New file at project root. JSON so both Python and TypeScript read it natively.

```json
{
  "zip": "21015",
  "locality": {
    "name": "Bel Air, Maryland",
    "state": {
      "name": "Maryland",
      "abbrev": "MD",
      "body": "Maryland General Assembly",
      "openstates_jurisdiction": "ocd-jurisdiction/country:us/state:md/government",
      "legiscan_state_id": 20
    },
    "county": {
      "name": "Harford County",
      "body": "Harford County Council",
      "scrapers": {
        "ecode360": { "code": "HA0904" },
        "harford_bills": { "url": "https://apps.harfordcountymd.gov/Legislation/Bills" }
      }
    },
    "municipal": {
      "name": "Town of Bel Air",
      "body": "Town of Bel Air Board of Commissioners",
      "website": "https://www.belairmd.org",
      "scrapers": {
        "ecode360": { "code": "BE2811" },
        "belair_legislation": { "url": "https://www.belairmd.org/213/Legislation" }
      }
    }
  },
  "display": {
    "title": "CivicLens",
    "subtitle": "Bel Air, MD",
    "description": "Plain-language access to the laws that affect you.",
    "footer_attribution": "Data sourced from Maryland General Assembly, Harford County, and Town of Bel Air public records.",
    "example_questions": [
      "What are the fence regulations in Bel Air?",
      "Can I run a home business in a residential zone?",
      "What are the noise ordinance hours?",
      "What bills are being considered in the Maryland General Assembly that affect Harford County?"
    ]
  }
}
```

County and municipal can be `null` if a fork doesn't have those jurisdictions. Scraper keys map to Python module names — if a key is absent, that scraper is skipped.

---

## Part 2: Config Loaders

### Python — modify `src/lib/config.py`
- Add `_load_locality()` that reads `civic-lens.config.json` from project root
- Store in module-level `LOCALITY` dict
- Replace hardcoded jurisdiction fields (lines 47-50) with config-driven values
- Add accessors: `get_locality()`, `get_state_config()`, `get_county_config()`, `get_municipal_config()`

### TypeScript — new `src/lib/locality.ts`
- Import `civic-lens.config.json` directly (Next.js bundles JSON at build time)
- Export typed accessors for UI components and server-side code
- `resolveJsonModule` is already enabled in Next.js by default

---

## Part 3: File Changes

### Ingestion clients (replace constants with config reads)
| File | Change |
|------|--------|
| `src/ingestion/clients/openstates.py` | `MARYLAND_JURISDICTION` (line 32) → `get_state_config()["openstates_jurisdiction"]` |
| `src/ingestion/clients/legiscan.py` | `MARYLAND_STATE_ID = 20` (line 43) → `get_state_config()["legiscan_state_id"]` |

### Scrapers (parameterize + config guards)
| File | Change |
|------|--------|
| `src/ingestion/scrapers/ecode360.py` | `BEL_AIR_CODE`/`HARFORD_COUNTY_CODE` (lines 35-36) → read from config scraper sections |
| `src/ingestion/scrapers/belair_legislation.py` | URL constants (lines 33-34) → from municipal scraper config; skip if not configured |
| `src/ingestion/scrapers/harford_bills.py` | `BILLS_URL` (line 41) → from county scraper config; skip if not configured |

### Pipeline
| File | Change |
|------|--------|
| `src/pipeline/normalize.py` | Body names (lines 123, 157, 199) → from config. eCode360 code mapping (lines 219-224) → config-driven lookup |

### Frontend (all display strings from config)
| File | Change |
|------|--------|
| `src/app/layout.tsx` | Metadata title (line 6), footer text (line 44) → from locality config. Add `/stats` nav link. |
| `src/app/page.tsx` | Subtitle text (line 101) → config-driven |
| `src/app/chat/page.tsx` | Example questions (lines 29-33), subtitle → from config |
| `src/app/about/page.tsx` | All locality text → from config |
| `src/lib/rag.ts` | System prompt (line 142) → dynamically built from config jurisdictions |

---

## Part 4: Stats Page

### API Route — `src/app/api/stats/route.ts` (new)

GET endpoint returning:
- **Locality info**: from config (zip, jurisdiction names)
- **Data sources**: query `ingestion_runs` for latest run per source (status, timestamp, record counts)
- **Record counts**: COUNT(*) on `bronze_documents`, `legislative_items`, `code_sections`, `document_chunks`
- **Pipeline health**: embedding coverage % (chunks vs Silver records)

### Page — `src/app/stats/page.tsx` (new)

Server component that queries Supabase directly (no API hop needed):
1. **Locality card** — zip code, configured jurisdictions
2. **Data sources table** — source name, last run time (relative), status badge, records fetched
3. **Database counts** — Bronze / Silver / Gold stat cards
4. **Pipeline health** — embedding coverage bar

### Nav — add "Stats" link in `layout.tsx` nav (after "About")

---

## Part 5: Implementation Order

1. Create `civic-lens.config.json` with Bel Air values
2. Create `src/lib/locality.ts` (TypeScript loader)
3. Modify `src/lib/config.py` (Python loader)
4. Update ingestion clients (`openstates.py`, `legiscan.py`)
5. Update scrapers (`ecode360.py`, `belair_legislation.py`, `harford_bills.py`)
6. Update pipeline (`normalize.py`)
7. Update frontend (`layout.tsx`, `page.tsx`, `chat/page.tsx`, `about/page.tsx`, `rag.ts`)
8. Create stats API + page (`api/stats/route.ts`, `stats/page.tsx`)
9. Update `.env.example` docs

Steps 4-7 can be parallelized after 1-3. Step 8 only depends on 1-3.

---

## Verification

1. `python -c "from src.lib.config import get_locality; print(get_locality())"` — confirm Python reads config
2. `npm run build` — confirm TypeScript imports resolve and build succeeds
3. `npm run dev` — check all pages render with config-driven text (no hardcoded "Bel Air")
4. `grep -rn "Bel Air\|21015\|Harford\|Maryland" src/ --include='*.py' --include='*.ts' --include='*.tsx' | grep -v config | grep -v locality` — should return 0 hits outside config/locality files
5. Visit `/stats` — confirm it renders jurisdiction info and data freshness
6. `pytest tests/` — existing tests still pass
