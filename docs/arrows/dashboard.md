# Arrow: dashboard

Legislative tracker dashboard: filterable views of active/proposed legislation across all three jurisdictions, upcoming meetings, and recent changes.

## Status

**MAPPED** - 2026-03-14. Requirements defined in HLD G2; UI not yet designed or built.

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
- src/components/LegislativeTracker.tsx — main dashboard component
- src/components/FilterBar.tsx — jurisdiction/status/type/date filters
- src/components/LegislativeCard.tsx — individual item display
- src/components/MeetingCalendar.tsx — upcoming meetings view
- src/api/dashboard/route.ts — API routes for dashboard data

## Architecture

**Purpose:** Provide a visual overview of legislative activity across state, county, and municipal layers. Server-rendered from Silver/Gold layer data. The dashboard answers "what's happening?" while the chat answers "what does the law say?"

**Key Components:**
1. Legislative tracker — filterable list/card view of legislative_items by jurisdiction, status, type, date range
2. Filter bar — jurisdiction toggle (State / County / Municipal / All), status filter, type filter, search
3. Legislative card — title, status badge, jurisdiction label, last action, date, link to source
4. Meeting calendar — upcoming meetings from CivicPlus AgendaCenter data
5. Recent changes feed — chronological list of latest legislative actions across all jurisdictions

## EARS Coverage

See spec file in References above.

## Key Findings

None yet — UNMAPPED.

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
