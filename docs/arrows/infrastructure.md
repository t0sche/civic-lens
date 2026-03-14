# Arrow: infrastructure

Supabase database, Vercel deployment, GitHub Actions CI/CD, and project configuration.

## Status

**MAPPED** - 2026-03-14. HLD defines technology choices; schemas and deployment config not yet created.

## References

### HLD
- docs/high-level-design.md §4.2 (Component Summary), §5 (Design Decisions D2, D5)

### LLD
- docs/llds/infrastructure.md (created 2026-03-14)

### EARS
- docs/specs/infrastructure-specs.md (23 specs: 23 active, 0 deferred)

### Tests
- tests/ (created 2026-03-14)

### Code
- supabase/migrations/ — database schemas
- .github/workflows/ — GitHub Actions cron jobs
- vercel.json — Vercel configuration
- src/lib/supabase.ts — Supabase client

## Architecture

**Purpose:** Foundation layer that all other arrows depend on. Provides data storage (Supabase Postgres + pgvector), compute for ingestion (GitHub Actions), and serving infrastructure (Vercel).

**Key Components:**
1. Supabase project — Postgres with pgvector extension, Bronze/Silver/Gold schemas
2. GitHub Actions workflows — cron-scheduled ingestion runs, failure alerting
3. Vercel deployment — Next.js frontend + serverless API routes
4. Environment management — API keys for Open States, LegiScan, Claude, Gemini

## EARS Coverage

See spec file in References above.

## Key Findings

None yet — UNMAPPED.

## Work Required

### Must Fix
1. Create Supabase project and enable pgvector extension
2. Write migration files for Bronze/Silver/Gold table schemas
3. Configure Vercel project linked to repo
4. Set up GitHub Actions workflow skeleton with cron triggers
5. Environment variable management (secrets for API keys)

### Should Fix
1. Database connection pooling configuration for serverless (Supabase has built-in)
2. Row-level security policies (even though no auth for MVP, good hygiene)

### Nice to Have
1. Terraform/Pulumi IaC for reproducible setup
2. Local development environment with Docker Compose
