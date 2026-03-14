# Infrastructure

**Created**: 2026-03-14
**Status**: Design Phase
**HLD Reference**: §4.2 Component Summary, §5 D2 (Supabase), D5 (GitHub Actions)

## Context and Design Philosophy

Infrastructure is the foundation layer that every other arrow depends on. The guiding principle is **minimum viable ops**: a solo maintainer should spend zero time on infrastructure once it's running. Every choice optimizes for free-tier eligibility, managed services, and git-tracked configuration.

The three infrastructure pillars are: Supabase (data), Vercel (serving), and GitHub Actions (compute for ingestion). All three have generous free tiers and require no server management.

## Supabase Configuration

### Project Setup

A single Supabase project hosts all three medallion layers in one Postgres database. The pgvector extension must be enabled at project creation time — it cannot be added retroactively on the free tier.

**Free tier constraints that shape the design:**
- 500MB database storage — this is the binding constraint. Bronze layer raw content (full bill JSON, scraped HTML) will consume the most space. At ~5KB average per Bronze document and ~2,000 legislative items + ~500 code sections initially, that's roughly 12MB. Growth comes from meeting minutes PDFs (post-extraction text) and historical accumulation. The 500MB ceiling is comfortable for MVP but will require monitoring.
- 1GB file storage — used for downloaded PDFs before text extraction.
- 50,000 monthly active users — irrelevant at Bel Air scale.
- 500MB bandwidth/day — sufficient for dashboard SSR + chat API calls.

**Database connection strategy:** Supabase provides a connection pooler (PgBouncer) by default. Vercel serverless functions must use the pooled connection string (`db.*.supabase.co:6543`) to avoid exhausting Postgres connection limits. Python ingestion scripts running in GitHub Actions can use the direct connection (`db.*.supabase.co:5432`) since they're long-running single-connection processes.

### Schema Design

Three schemas logically separate the medallion layers, though all live in the `public` schema on the free tier (custom schemas require the Pro plan):

**Bronze tables** store raw ingested data faithfully. The `content_hash` column enables change detection — if a re-scraped document produces the same hash, the pipeline skips it. The `(source, source_id)` unique constraint ensures idempotent upserts.

**Silver tables** (`legislative_items`, `code_sections`, `meeting_records`) normalize heterogeneous sources into queryable schemas. These are the primary data model for the dashboard and the source truth for embedding generation.

**Gold table** (`document_chunks`) stores text chunks with pgvector embeddings. The HNSW index provides fast approximate nearest-neighbor search. Index parameters (`m=16, ef_construction=64`) are tuned for the expected corpus size (~5,000 chunks) — larger corpora would benefit from higher values.

**Operational table** (`ingestion_runs`) tracks pipeline health. Each scraper/client records its run status, enabling freshness monitoring and failure alerting.

### Row-Level Security

MVP runs without authentication (no user accounts), but RLS policies should be configured defensively:

- All tables: `SELECT` enabled for the `anon` role (public read access for the dashboard and chat)
- All tables: `INSERT`, `UPDATE`, `DELETE` restricted to the `service_role` key (only the ingestion pipeline and API routes can write)
- `ingestion_runs`: restricted to `service_role` entirely (operational data, not user-facing)

### Migration Strategy

Migrations are plain SQL files in `supabase/migrations/`, numbered sequentially. They're applied via the Supabase CLI (`supabase db push`) or the dashboard SQL editor. For a solo maintainer, the CLI approach is preferable because it keeps migrations version-controlled.

The initial migration (`001_initial_schema.sql`) creates all tables, enums, indexes, and triggers. Subsequent migrations add RPC functions (`002_vector_search_rpc.sql`). Future migrations should follow the pattern: one migration per logical change, with both "up" and implicit "down" (via re-creation).

## Vercel Deployment

### Project Configuration

The Next.js app deploys to Vercel's free Hobby plan, which provides:
- Serverless functions (API routes) with 10-second execution timeout on free tier
- SSR/SSG for dashboard pages
- Automatic HTTPS and CDN
- Git-triggered deployments (push to `main` = deploy)

The 10-second serverless timeout is the critical constraint for the chat API route. The RAG pipeline must complete embedding → retrieval → model call → response within 10 seconds. This is achievable for Gemini Flash (<3s typical) but tight for Claude API calls under load (~5-8s). If timeouts become an issue, the mitigation is Vercel's streaming response support, which resets the timeout on each chunk.

**Environment variables** are configured in the Vercel dashboard, not committed to the repo. Required variables match `.env.example`: Supabase URL/keys, API keys for Open States, LegiScan, Anthropic, Google AI.

### Routing

Next.js App Router handles all routing:
- `/` — Dashboard (server component, SSR)
- `/chat` — Chat interface (client component)
- `/about` — Static page
- `/api/chat` — Chat API route (serverless function)

No custom `vercel.json` needed for basic deployment. If edge functions or custom headers become necessary, add `vercel.json` then.

## GitHub Actions

### Workflow Design

A single workflow file (`.github/workflows/ingest.yml`) handles all ingestion with three jobs:

1. **ingest-state-bills** — runs every 6 hours, calls Open States API client
2. **ingest-local-data** — runs daily at 6 AM ET, runs scrapers (eCode360, Bel Air legislation)
3. **normalize-and-embed** — depends on both ingestion jobs, runs Bronze→Silver→Gold pipeline

Job dependencies ensure normalization only runs after successful ingestion. The `always()` condition on normalize-and-embed means it runs even if one ingestion source fails (partial data is better than no data).

**Free tier budget:** GitHub Actions provides 2,000 minutes/month for public repos (unlimited) or 500 minutes/month for private repos. Each ingestion run is estimated at 2-5 minutes. At 4 state runs + 1 local run per day = ~150 runs/month × 3 minutes = ~450 minutes. This fits within the private repo limit but is tight — if the repo is public, it's a non-issue.

### Secrets Management

GitHub repository secrets store API keys and Supabase credentials. Required secrets:
- `SUPABASE_URL` (maps to `NEXT_PUBLIC_SUPABASE_URL`)
- `SUPABASE_SERVICE_ROLE_KEY`
- `OPENSTATES_API_KEY`
- `LEGISCAN_API_KEY`
- `GOOGLE_AI_API_KEY`
- `ANTHROPIC_API_KEY` (not used in ingestion, but needed if enrichment uses Claude)

### Failure Alerting

The `notify-on-failure` job runs when any upstream job fails. For MVP, it logs to the GitHub Actions console. Post-MVP, this should send a notification (GitHub has built-in email for failed workflows; Slack webhook or email can be added).

The `ingestion_runs` table in Supabase provides a secondary monitoring surface — a simple dashboard query showing runs with `status = 'failed'` or `completed_at IS NULL` (stuck runs) catches issues the GitHub notification might miss.

## Environment Management

### Local Development

Developers (i.e., you) copy `.env.example` to `.env.local` and fill in API keys. The Python config module (`src/lib/config.py`) loads `.env.local` via `python-dotenv`. The Next.js framework automatically loads `.env.local` for the frontend.

All environment variables follow the convention:
- `NEXT_PUBLIC_*` — safe for browser exposure (Supabase anon key, URL)
- Everything else — server-only (service role key, API keys)

### API Key Procurement

Getting started requires creating accounts and generating keys for:
1. **Supabase** — create project at supabase.com, copy URL + anon key + service role key
2. **Open States** — register at openstates.org/accounts/signup/ (free, instant)
3. **LegiScan** — register at legiscan.com/user/register (free, 30K queries/month)
4. **Google AI** — enable Gemini API at ai.google.dev (free tier, 1,500 requests/day for embeddings)
5. **Anthropic** — create key at console.anthropic.com (pay-per-use for Claude Sonnet calls)

Total estimated monthly cost at MVP traffic: $0-10, dominated by Claude API calls for complex queries.

## Open Questions & Future Decisions

### Resolved
1. ✅ Supabase over self-hosted Postgres — managed service wins for solo maintainer
2. ✅ pgvector over separate vector store — one fewer service to manage
3. ✅ GitHub Actions over dedicated scheduler — free, git-tracked, sufficient cadence

### Deferred
1. Whether to move Bronze layer raw content to Supabase Storage (S3-compatible) if the 500MB DB limit becomes tight — monitor after Phase 4 when PDFs are ingested
2. Local development Docker Compose for running Supabase locally — unnecessary until collaboration or offline dev becomes important
3. Terraform/Pulumi for reproducible infrastructure — defer until the project is forked for other jurisdictions

## References

- Supabase free tier limits: https://supabase.com/pricing
- Vercel Hobby plan limits: https://vercel.com/pricing
- GitHub Actions minutes: https://docs.github.com/en/billing/managing-billing-for-github-actions
- pgvector HNSW tuning: https://github.com/pgvector/pgvector#hnsw
