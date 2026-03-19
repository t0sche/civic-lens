# Arrow: dashboard

Legislative tracker dashboard: filterable views of active/proposed legislation across all three jurisdictions, upcoming meetings, and recent changes.

## Status

**IMPLEMENTED** - 2026-03-19. Dashboard is live in src/app/page.tsx with jurisdiction filtering, legislative cards, and jurisdiction views. Component decomposition from the original plan was not done — functionality is monolithic.

## References

### HLD
- docs/high-level-design.md §2 G2 (dashboard goal), §3 (personas), §8 Phase 3

### LLD
- docs/llds/dashboard.md (created 2026-03-14)

### EARS
- docs/specs/dashboard-specs.md (26 specs: 20 active, 6 deferred)

### Tests
- tests/api/test_dashboard_queries.py

### Code
- src/app/page.tsx — dashboard implemented monolithically (filtering, cards, layout all in one file)
- src/api/dashboard/route.ts — API route for dashboard data

## Architecture

**Purpose:** Provide a visual overview of legislative activity across state, county, and municipal layers. Server-rendered from Silver/Gold layer data. The dashboard answers "what's happening?" while the chat answers "what does the law say?"

**Key Components:**
1. Legislative tracker — filterable list/card view of legislative_items by jurisdiction (status, type, and date range filters planned but not yet implemented)
2. Filter bar — jurisdiction toggle (State / County / Municipal / All); additional controls for status, type, and search are planned
3. Legislative card — title, status badge, jurisdiction label, last action, date, link to source
4. Meeting calendar — upcoming meetings from CivicPlus AgendaCenter data
5. Recent changes feed — chronological list of latest legislative actions across all jurisdictions

## EARS Coverage

See spec file in References above.

## Key Findings

- Dashboard is fully implemented in `src/app/page.tsx` as a monolith rather than the planned component decomposition (LegislativeTracker.tsx, FilterBar.tsx, etc. were never created).
- Filtering by jurisdiction is functional; status, type, and date range filters are not yet implemented.
- Meeting calendar and recent changes feed are not yet implemented (deferred to Phase 9).

## Work Required

### Must Fix
1. Dashboard page with server-side data fetching from Silver layer
2. Filter bar component (jurisdiction, status, type, date range)
3. Legislative item card component with source linking
4. API route for filtered legislative_item queries

### Should Fix
1. Upcoming meetings calendar from AgendaCenter data
2. Recent changes / activity feed (sorted by last_action_date)
3. Data freshness indicator ("Last updated: 3 hours ago")

### Nice to Have
1. Topic-based views (zoning, taxes, public safety groupings)
2. RSS/Atom feed output for the dashboard data
3. Mobile-responsive layout
