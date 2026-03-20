# Arrow: infrastructure

Supabase database, Vercel deployment, GitHub Actions CI/CD, and project configuration.

## Status

**PARTIALLY_IMPLEMENTED** - 2026-03-19. Database schemas, CI/CD workflows, Vercel deployment, and environment config are all in place. RLS policies (INFRA-SEC-001/002/003) not yet implemented — anon key has unrestricted read access to all tables.

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

- Supabase schema (4 migrations), GitHub Actions cron jobs, and Vercel deployment all verified in place.
- **HIGH**: No RLS policies in any migration (001–004). The anon key has full SELECT access to all Silver and Gold tables (legislative_items, code_sections, document_chunks, ingestion_runs). INFRA-SEC-001/002/003 are not implemented.
- **MEDIUM**: The `civic-lens.config.json` locality config system (src/lib/config.py) has no corresponding EARS specs. It is used by normalizers, embedder, and rag.ts prompt builder.
- Next hardening step: migration 005_rls_policies.sql — enable RLS on all tables, grant anon SELECT only on legislative_items/code_sections/document_chunks, restrict ingestion_runs to service_role.

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
