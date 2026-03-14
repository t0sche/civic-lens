# Dashboard: Legislative Tracker

**Created**: 2026-03-14
**Status**: Design Phase
**HLD Reference**: §2 G2, §3 Personas, §8 Phase 3

## Context and Design Philosophy

The dashboard answers "what's happening?" while the chat answers "what does the law say?" It's a server-rendered view of the Silver layer that gives residents and civic participants a single feed of legislative activity across all three jurisdictions.

The design philosophy is **information density without overwhelm**. A resident scanning the dashboard should immediately see what's active, what's new, and which jurisdiction each item belongs to — without needing to understand government process terminology.

## Page Architecture

The dashboard is a single Next.js server component that queries the Silver layer at render time (SSR). No client-side data fetching — the page loads with all data present, which is better for SEO and first-contentful-paint. The trade-off is that data is as fresh as the last server render, not real-time, but legislative data changes daily at most, so this is fine.

### Data Flow

```
Browser request → Vercel Edge → Next.js server component
                                      ↓
                               Supabase query (legislative_items)
                                      ↓
                               Render HTML with data
                                      ↓
                               Return to browser
```

The Supabase query uses the `service_role` key server-side (never exposed to the browser). Query parameters come from URL search params (`?jurisdiction=STATE`), validated server-side.

## UI Components

### Filter Bar

A horizontal row of pill-shaped buttons for jurisdiction filtering:
- **All** (default) — shows items from all three jurisdictions
- **State** — Maryland General Assembly items only
- **County** — Harford County Council items only
- **Municipal** — Town of Bel Air items only

Filters work via URL search params (`/?jurisdiction=COUNTY`), making them shareable and bookmarkable. The active filter gets a dark background; inactive filters get a light gray background.

Post-MVP filter additions:
- **Status filter**: Active / Passed / Failed / All
- **Type filter**: Bills / Ordinances / Resolutions / All
- **Date range**: Last 30 days / Last 90 days / This session / All
- **Search**: Free-text search across titles and summaries

### Legislative Item Card

Each legislative item renders as a card with:

**Row 1 — Badges**: Jurisdiction badge (color-coded: purple=State, teal=County, sky=Municipal) + Status badge (color-coded: green=enacted/approved, blue=introduced, yellow=in committee, red=vetoed/rejected, amber=pending, gray=expired/unknown) + Source ID (e.g., "HB 100") in muted text.

**Row 2 — Title**: Linked to source URL (opens in new tab). Truncated at 2 lines with CSS `line-clamp-2`. The link takes the user directly to the official source (Open States page, eCode360 section, CivicPlus document).

**Row 3 — Summary** (if available): Plain-language summary in smaller text, also truncated at 2 lines.

**Row 4 — Metadata**: Governing body name + Last action date + Last action description (truncated).

### Status Color Mapping

Status colors follow a traffic-light metaphor that maps to legislative outcomes:

| Status | Color | Meaning |
|--------|-------|---------|
| INTRODUCED | Blue | New, early stage |
| IN_COMMITTEE | Yellow | Under review |
| PASSED_ONE_CHAMBER | Indigo | Progressing |
| ENACTED / APPROVED / EFFECTIVE | Green | Became law |
| VETOED / REJECTED | Red | Did not pass |
| PENDING | Amber | Awaiting action |
| TABLED | Orange | Paused |
| EXPIRED | Gray | No longer active |
| UNKNOWN | Gray (muted) | Status not determined |

### Jurisdiction Color Coding

Consistent colors across the entire application:
- **State** (purple): `bg-purple-100 text-purple-800`
- **County** (teal): `bg-teal-100 text-teal-800`
- **Municipal** (sky blue): `bg-sky-100 text-sky-800`

These colors appear in dashboard badges, chat source citations, and any future jurisdiction references.

### Empty State

When no items match the current filter (or the database is empty), a dashed-border empty state displays:
- Primary message: "No legislative items found."
- Secondary: "Data ingestion may not have run yet. Check the ingestion pipeline status in GitHub Actions."

This honest empty state prevents confusion during initial setup and pipeline debugging.

## Query Strategy

### Default Query

```sql
SELECT * FROM legislative_items
ORDER BY last_action_date DESC NULLS LAST
LIMIT 50
```

The 50-item limit keeps initial page load fast. Pagination (offset-based or cursor-based) is a post-MVP enhancement — at MVP scale, 50 items covers the most recent month of activity across all jurisdictions.

### Filtered Query

```sql
SELECT * FROM legislative_items
WHERE jurisdiction = $1
ORDER BY last_action_date DESC NULLS LAST
LIMIT 50
```

The `jurisdiction` parameter is validated server-side against the `JurisdictionLevel` enum before query execution. Invalid values default to "ALL" (no filter).

### Performance

At ~2,500 Silver records, these queries complete in <50ms even without materialized views. The `idx_legitem_lastaction` index supports the ORDER BY clause. The `idx_legitem_jurisdiction` index supports the WHERE filter.

If the dataset grows to 10,000+ records, consider:
1. Materialized views for the default dashboard view
2. Cursor-based pagination (ORDER BY `last_action_date, id`)
3. Pre-computed jurisdiction counts for dashboard header stats

## Post-MVP Dashboard Features

### Upcoming Meetings Calendar

A card or section showing the next 5-10 upcoming meetings from CivicPlus AgendaCenter data. Requires `meeting_records` to be populated (Phase 4). Display format:
- Date + Time
- Body name (e.g., "Board of Town Commissioners")
- Jurisdiction badge
- Link to agenda PDF if available

### Recent Changes Feed

A chronological feed of the most recent legislative actions across all jurisdictions, similar to a news feed. Each entry shows: date, action description, item title, jurisdiction. This provides a "what happened this week" view that's more temporal than the default status-grouped view.

### Data Freshness Indicator

A subtle indicator in the dashboard header showing when data was last updated per source:
- "State bills: updated 3 hours ago" (green)
- "Town ordinances: updated 18 hours ago" (green)
- "County council: updated 4 days ago" (red — possible pipeline issue)

Implemented by querying `MAX(completed_at)` from `ingestion_runs` grouped by source, filtered to `status = 'success'`.

### Topic Filtering

Once the enrichment pipeline generates topic tags, the dashboard can offer topic-based views: "Show me everything related to zoning" or "What's happening with taxes?" This requires the `tags` GIN index on `legislative_items` and a multi-select filter in the UI.

## Open Questions & Future Decisions

### Resolved
1. ✅ SSR over client-side fetching — better first paint, SEO, no loading spinner for initial data
2. ✅ URL-based filters — shareable, bookmarkable, simple to implement
3. ✅ 50-item limit without pagination — sufficient for MVP scale
4. ✅ Traffic-light status colors — intuitive mapping to legislative outcomes

### Deferred
1. Pagination — add when the dataset exceeds 50 meaningful items per filter
2. Search — free-text search across titles and summaries, requires full-text index or Silver-layer tsvector
3. RSS/Atom output — publish the dashboard data as a subscribable feed
4. Mobile-responsive layout — Tailwind handles basic responsiveness, but the card layout may need optimization for narrow screens

## References

- Next.js App Router server components: https://nextjs.org/docs/app/building-your-application/rendering/server-components
- Tailwind CSS: https://tailwindcss.com/docs
