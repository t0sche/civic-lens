# CivicLens Data Source Expansion Research
**Date:** 2026-03-19
**Status:** Research complete — implementation phased across Phase 9–11+

This document captures 60+ additional civic data sources identified for CivicLens (Bel Air, MD 21015). Sources are tiered by access method and phased by implementation priority.

---

## Tier 1 — Structured APIs (Free, Documented, High Reliability)

### Federal Legislative & Regulatory

| Source | Endpoint | Auth | Rate Limit | Phase | Notes |
|--------|----------|------|-----------|-------|-------|
| **Congress.gov API** | `api.congress.gov` | Free api.data.gov key | 5,000 req/hr | **9** | Replaces defunct ProPublica Congress API (shut down Feb 4, 2025). Bills, amendments, members, committees, nominations from 81st Congress onward. MD-01 covers Harford County. |
| **GovInfo API** | `api.govinfo.gov` | Free api.data.gov key | Generous | **9** | Full text of bills, Federal Register, CFR, Congressional Record. Bulk download + document-level API. |
| **Regulations.gov** | `api.regulations.gov` | Free key | GET unrestricted | **10** | Federal rulemaking. POST restricted since Aug 2025 but GET still works. |

### Federal Grants & Spending

| Source | Endpoint | Auth | Rate Limit | Phase | Notes |
|--------|----------|------|-----------|-------|-------|
| **USA Spending API** | `api.usaspending.gov` | None required | Generous | **9** | Federal contracts and grants. Filter by Harford County FIPS 24025 or ZIP 21015. Aberdeen Proving Ground makes this unusually relevant — large DoD contracts affect local economy. |
| **OpenFEC API** | `api.open.fec.gov` | Free api.data.gov key | 1,000 req/hr | **10** | Official FEC contribution/expenditure data. MD-01 House, MD Senate races. |
| **OpenSecrets API** | `opensecrets.org/api` | Free key (non-commercial) | Moderate | **11** | Federal campaign finance, lobbying. Supplements OpenFEC with curated summaries. |

### Federal Contextual Data

| Source | Endpoint | Auth | Rate Limit | Phase | Notes |
|--------|----------|------|-----------|-------|-------|
| **Census / ACS API** | `api.census.gov` | Free key | Unlimited | **10** | Harford County FIPS 24025. Key tables: B01003 (population ~265K), B19013 (median income), B25077 (median home value), B17001 (poverty). ACS 5-year at block-group level; ACS 1-year at county level. |
| **FEMA NFHL** | `hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer` | None | Generous | **10** | National Flood Hazard Layer. Spatial queries by coordinates or county. Returns flood zone (AE, A, X, VE), base flood elevations, floodway status. Harford County has full coverage. |
| **EPA ECHO** | `echo.epa.gov/tools/web-services/` | None | Updated weekly | **10** | Enforcement and compliance data for regulated facilities. Filter by county or ZIP. Inspection history, violations, penalties, pollutant data. |
| **EPA Envirofacts DMAP** | `data.epa.gov/dmapservice/` | None | Generous | **10** | TRI releases, facility registry, RCRA hazardous waste, greenhouse gas. JSON/CSV. |
| **BLS LAUS** | `api.bls.gov/publicAPI/v2/timeseries/data/` | Free key | 500 req/day | **10** | Local Area Unemployment Statistics. Harford County series ID: `LAUCN240250000000003`. Recent data: avg weekly wage $1,353 Q1 2025; employment -0.8% YoY. |
| **HUD FMR API** | `huduser.gov/hudapi/public/fmr/data/` | Free token | Generous | **10** | Fair Market Rents by ZIP. 21015 in Baltimore-Columbia-Towson MSA. 2025 two-bedroom FMR: $1,965/month (14.5% above MD avg). Income limits, subsidized housing data. |
| **USDA NASS Quick Stats** | `quickstats.nass.usda.gov/api/` | Free key | 1M req/day | **11** | Agricultural data. Harford County: 1,831 farms per Census of Agriculture. |
| **Census Geocoder** | `geocoding.geo.census.gov/geocoder/` | None | Generous | **10** | Free address → lat/lon + census geography. Alternative to USPS (restricted to shipping). |

### Maryland State

| Source | Endpoint | Auth | Format | Phase | Notes |
|--------|----------|------|--------|-------|-------|
| **MGA Bulk CSV/JSON** | `mgaleg.maryland.gov/mgawebsite/Legislation/OpenData` | None | CSV/JSON | **9** | All bill metadata since 2013: number, sponsor, synopsis, status, progress, hearing dates, committees, passage, 79 subject categories. Updates throughout session. Docs: `mgaleg.maryland.gov/pubs-current/current-open-data-help.pdf` |
| **DLS RSS Feeds** | `dls.maryland.gov/feeds/` | None | RSS/XML | **9** | Department of Legislative Services. Real-time alerts for new publications and data updates. Lightweight integration. |
| **MD Open Data Portal** | `opendata.maryland.gov` | None (SODA) | JSON/CSV/GeoJSON | **10** | 1,000+ datasets. Free, no key. Extensive civic-relevant data not yet catalogued. |
| **MD Judiciary RSS** | `mdcourts.gov/rss.xml` | None | RSS/XML | **10** | Appellate opinions, press releases, judicial vacancies. |

### Local GIS (ArcGIS REST)

| Source | Endpoint | Auth | Format | Phase | Notes |
|--------|----------|------|--------|-------|-------|
| **Harford County ArcGIS Hub** | `harford-county-gis-hub-harfordgis.hub.arcgis.com` | None | GeoJSON/CSV/Shapefile | **9** | Parcels, zoning, land use, floodplains, wetlands, municipal boundaries, road centerlines, public facilities, aerial photography. REST API access. NOT federated into MD Open Data Portal. |
| **Bel Air ArcGIS Hub** | `toba-data-hub-belairmd.hub.arcgis.com` | None | GeoJSON/CSV/Shapefile/KML | **9** | Zoning, property boundaries, public services, parks, infrastructure. Newly discovered — not previously tracked. |
| **Harford Development Review Dashboard** | `harfordgis.maps.arcgis.com/apps/dashboards/a4ee28c671ca4980889ad2d1b3c173ff` | None | ArcGIS Feature Service | **10** | Active concept plans, site plans, subdivisions, community input meetings. Scrapable via REST API calls. |
| **iMAP GIS (State)** | `data.imap.maryland.gov` | None | ArcGIS REST/GeoJSON | **11** | Statewide parcels, tax maps, boundaries, environmental layers. |

---

## Tier 2 — Structured Scraping (RSS, HTML, predictable structure)

| Source | URL | Method | Phase | Notes |
|--------|-----|--------|-------|-------|
| **Bel Air CivicPlus RSS (11 boards)** | `belairmd.org/rss.aspx` | RSS polling | **9** | 11 board/commission agendas + Alert Center, Calendar, News Flash, Jobs. Pattern: `belairmd.org/RSSFeed.aspx?ModID={id}&CID={cat}`. Lowest-effort high-value integration. |
| **Harford County RSS** | `harfordcountymd.gov/RSS.aspx` | RSS polling | **9** | Government news, DPW alerts, economic development, emergency alerts. Standard RSS. |
| **Harford Zoning Board of Appeals** | `hcgweb01.harfordcountymd.gov/Legislation/Zonings` | HTTP + HTML parse | **9** | **Same ASP.NET app as harford_bills.py.** Minimal new code needed — add ZBA case type to existing scraper. |
| **Bel Air DocumentCenter** | `belairmd.org/DocumentCenter` | Sequential crawl | **10** | Sequential numeric IDs: `/DocumentCenter/View/{ID}/`. 10 categories: budgets FY2012–2026, audits 2015–2024, capital plans, BOA minutes, Planning minutes, Historic Preservation minutes, resolutions, ordinances. |
| **Bel Air Archive Center** | `belairmd.org/Archive.aspx` | HTML parse | **10** | Historical documents. Overlaps with DocumentCenter. |
| **Bel Air Development Proposals** | `belairmd.org/622/Development-Proposals` | HTML parse | **11** | Site plans, landscape plans, elevations, staff reports. Updated monthly for Planning Commission (1st Thu) and BOA (4th Tue). Archived at `/661/Archived-Development-Proposals`. |
| **Swagit/Granicus Video Archives** | `harfordcountymd.new.swagit.com/views/369` | HTML parse | **11** | County meeting video recordings back to 2011, with linked agendas. Video URLs + metadata. |
| **MD Judiciary RSS** | `mdcourts.gov/rss.xml` | RSS polling | **10** | Appellate opinions, judicial news. Redesigned portal launched March 14, 2026 — no API. |
| **Harford County ePermit Center** | `epermitcenter.harfordcountymd.gov` | Investigate EnerGov REST | **11** | Tyler Technologies EnerGov platform. No documented public API but EnerGov sometimes exposes undocumented REST endpoints. |
| **HCPS Board of Education** | `hcps.org/boe/boeagenda.aspx` | HTML parse | **11** | BOE agendas, budget PDFs, meeting livestreams. 37,855 students, 55 schools (9/30/2024). |
| **MD Register (biweekly)** | `dsd.maryland.gov/Pages/MDRegister.aspx` | HTML scrape (3 free issues) | **11** | Proposed regulations. Only 3 most recent biweekly issues free online. No RSS or API. Scrape on biweekly cadence. |

---

## Tier 3 — PDF/HTML Only (Valuable, Higher Effort)

| Source | URL | Format | Priority | Notes |
|--------|-----|--------|----------|-------|
| MGA Bill Text | `mgaleg.maryland.gov/{SESSION}/bills/{chamber}/{bill}{version}.pdf` | PDF | High | Predictable URL pattern. Plain-text API absent. |
| MGA Fiscal & Policy Notes | Individual bill detail pages | PDF links | Medium | No bulk access. |
| Harford County Annual Budget | `harfordcountymd.gov/1531/Budget-Management` | PDF | Medium | Archives FY2017+. Structured tabular data. |
| Harford County ACFR | `harfordcountymd.gov/1935/Financial-Statements` | PDF | Medium | FY2008–FY2024. |
| Harford Monthly Permit Reports | `harfordcountymd.gov/2163/Data-Reports` | PDF | Medium | Residential permit activity, annual growth reports. |
| Bel Air Police Annual Reports | `belairmd.org/619/` | PDF | Low | UCR crime data, calls for service 2016–2023. |
| MD Judiciary Data Dashboards | `datadashboard.mdcourts.gov` | Web + downloadable | Low | Annual caseload data. |
| MD Transparency Portal | `mtp.maryland.gov` | Socrata dashboards | Low | Budget FY2017–FY2027, vendor payments, grants. |
| Comptroller Open Data | `marylandcomptroller.gov/reports/open-data.html` | CSV | Low | Tax revenue by type. |
| Election Results | `results.elections.maryland.gov` | CSV | Low | Precinct-level from 2020+. |
| MD Case Search (new) | `casesearch.courts.state.md.us` | HTML | Low | Launched March 14, 2026. Web-only, no API. |
| MD Land Records | `mdlandrec.net` | HTML + scanned images | Low | Free registration. Deeds, mortgages, liens. |

---

## Deprecated / Changed Sources

| Source | Status | Replacement |
|--------|--------|-------------|
| **ProPublica Congress API** | **DEFUNCT** (GitHub archived Feb 4, 2025) | **Congress.gov API** (`api.congress.gov`) |
| **Google Civic Information — Representatives** | **DEFUNCT** (turned down April 30, 2025) | **Cicero API** (commercial, credits) or OCD-ID lookups via remaining Divisions endpoint |
| **Regulations.gov POST API** | **Restricted** (Aug 2025) | GET endpoints still work |

---

## Third-Party Aggregators — Status Matrix

| Aggregator | Status | Cost | MD Coverage | Best Use |
|-----------|--------|------|-------------|---------|
| Plural/Open States | ✅ Active | Free tier | MD General Assembly | Already in use |
| Congress.gov API | ✅ Active | Free | Federal (complete) | **Priority — replaces ProPublica** |
| GovInfo API | ✅ Active | Free | Federal docs | Full text of bills, Federal Register |
| USA Spending | ✅ Active | Free | Harford by FIPS 24025 | Federal grants/contracts (APG) |
| OpenFEC | ✅ Active | Free | MD-01, MD Senate | Official FEC contribution data |
| OpenSecrets | ✅ Active | Free (non-commercial) | MD federal candidates | Campaign finance, lobbying |
| FollowTheMoney | ⚠️ Transitioning | Free (account) | MD state races | State-level campaign finance |
| Vote Smart | ✅ Active | Inquiry needed | Federal + state | Voting records, interest group ratings |
| Ballotpedia | ✅ Active | **$$$** | Comprehensive | Cost-prohibitive for civic projects |
| Cicero | ✅ Active | Commercial (credits) | All levels | Address→official lookup |
| LegiScan | ✅ Active (in use) | Free tier | MD General Assembly | Already in use |
| Regulations.gov | ⚠️ GET only | Free | Federal rulemaking | POST restricted Aug 2025 |
| Councilmatic | No MD instance | Free (open source) | None | Would require custom deployment |

---

## Strategic Gaps

1. **Maryland campaign finance (MD CRIS)** — 17 years of contribution data behind HTML-only search at `campaignfinance.maryland.gov`. No API, no bulk download. Gap unlikely to be filled by the state.

2. **Harford County non-federation** — Unlike Howard, Montgomery, and Baltimore County, Harford County is NOT federated into `opendata.maryland.gov`. County-level structured data limited to GIS layers.

3. **Public safety data** — Harford County Sheriff's Office does not publish structured crime statistics. No public safety crime data portal exists.

4. **MGA bill text** — No plain-text API for bill full text. PDF URLs are predictable but require ingestion-pdf pipeline (currently deferred).

---

## Implementation Notes

### eCode360 PDF (from .extra directory)
The eCode360 website provides downloadable PDFs of the full municipal code. These PDFs have been obtained and placed in `.extra/`. This enables text extraction without live scraping for initial load. See ingestion-pdf arrow for the extraction pipeline design.

### Aberdeen Proving Ground Context
USA Spending API filtered by FIPS 24025 reveals significant federal contracting activity driven by APG. This context is uniquely relevant for Harford County residents tracking economic and land-use impacts.

### Bel Air ArcGIS Hub Discovery
The Bel Air ArcGIS Hub at `toba-data-hub-belairmd.hub.arcgis.com` was not previously documented in the arrows. It provides REST API access to zoning, property boundaries, and infrastructure — the same data the chat answers questions about, but in structured GIS form.
