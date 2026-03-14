# Dashboard Specifications

**Design Doc**: `/docs/llds/dashboard.md`
**Arrow**: `/docs/arrows/dashboard.md`

## Legislative Tracker View

- [ ] **DASH-VIEW-001**: The system shall display a server-rendered page at `/` showing legislative items from the Silver layer, ordered by last_action_date descending with nulls last, limited to 50 items.
- [ ] **DASH-VIEW-002**: When a jurisdiction query parameter is present and valid (STATE, COUNTY, MUNICIPAL), the system shall filter legislative items to that jurisdiction only.
- [ ] **DASH-VIEW-003**: When the jurisdiction parameter is "ALL" or absent, the system shall display items from all jurisdictions.
- [ ] **DASH-VIEW-004**: If the jurisdiction parameter contains an invalid value, then the system shall default to "ALL" without returning an error.

## Filter Bar

- [ ] **DASH-FILTER-001**: The system shall display a horizontal row of jurisdiction filter buttons: All, State, County, Municipal.
- [ ] **DASH-FILTER-002**: The active jurisdiction filter shall be visually distinguished with a dark background, while inactive filters use a light gray background.
- [ ] **DASH-FILTER-003**: Each filter button shall link to the dashboard URL with the corresponding jurisdiction query parameter, making filter state bookmarkable and shareable.

## Legislative Item Card

- [ ] **DASH-CARD-001**: Each legislative item shall display a jurisdiction badge with color coding: purple for State, teal for County, sky blue for Municipal.
- [ ] **DASH-CARD-002**: Each legislative item shall display a status badge with color coding: green for enacted/approved/effective, blue for introduced, yellow for in-committee, indigo for passed-one-chamber, red for vetoed/rejected, amber for pending, orange for tabled, gray for expired/unknown.
- [ ] **DASH-CARD-003**: Each legislative item shall display the source_id (bill/ordinance number) in muted text adjacent to the badges.
- [ ] **DASH-CARD-004**: Each legislative item shall display the title, linked to the source_url (opening in a new tab) when a source_url is present.
- [ ] **DASH-CARD-005**: When a legislative item has a summary, the system shall display it below the title, truncated to 2 lines.
- [ ] **DASH-CARD-006**: Each legislative item shall display the governing body name, last_action_date, and last_action text in a metadata row.

## Empty State

- [ ] **DASH-EMPTY-001**: When no legislative items match the current filter, the system shall display a dashed-border empty state with the message "No legislative items found."
- [ ] **DASH-EMPTY-002**: The empty state shall include a secondary message: "Data ingestion may not have run yet. Check the ingestion pipeline status in GitHub Actions."

## Navigation

- [ ] **DASH-NAV-001**: The system shall display a top navigation bar with links to Dashboard (/), Ask a Question (/chat), and About (/about).
- [ ] **DASH-NAV-002**: The system shall display a footer on every page with a legal disclaimer: "CivicLens is not a law firm and does not provide legal advice. Information is provided for educational purposes only."
- [ ] **DASH-NAV-003**: The footer shall include a data source attribution: "Data sourced from Maryland General Assembly, Harford County, and Town of Bel Air public records."

## About Page

- [ ] **DASH-ABOUT-001**: The system shall provide a static About page at /about describing the project's purpose, data sources, disclaimers, and open-source status.
- [ ] **DASH-ABOUT-002**: The About page shall explicitly note that state regulations (COMAR) are not yet included due to technical and legal access constraints.

## Post-MVP Features

- [D] **DASH-MEET-001**: The system shall display an upcoming meetings section showing the next 5-10 meetings from CivicPlus AgendaCenter data with date, time, body name, jurisdiction badge, and agenda link.
- [D] **DASH-FRESH-001**: The system shall display a data freshness indicator showing the last successful ingestion time per source, color-coded green (<24h), yellow (24-72h), or red (>72h).
- [D] **DASH-FEED-001**: The system shall display a recent changes feed showing the most recent legislative actions across all jurisdictions in chronological order.
- [D] **DASH-TOPIC-001**: Where legislative items have populated tags, the system shall provide a topic filter allowing users to view items by topic category.
- [D] **DASH-SEARCH-001**: The system shall provide a free-text search field that searches across legislative item titles and summaries.
- [D] **DASH-PAGE-001**: When the dataset exceeds 50 items per filter, the system shall provide cursor-based pagination using (last_action_date, id) ordering.
