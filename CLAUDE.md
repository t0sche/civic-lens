# CLAUDE.md — CivicLens

## Project Overview

CivicLens is a civic transparency platform for Bel Air, Maryland (21015). It surfaces laws, proposed legislation, and government actions across three jurisdictions (Maryland State, Harford County, Town of Bel Air) via a RAG-powered chat interface and a legislative tracking dashboard.

## Development Workflow

This project uses **design-driven development**. Before making any code changes:

1. **Read `docs/arrows/index.yaml`** — understand what arrows exist and their status/dependencies
2. **Read the relevant arrow doc** in `docs/arrows/` — find LLD, spec, and code references
3. **Check for existing specs** in `docs/specs/` — verify intent coherence before changing code
4. **Follow the chain**: HLD → LLD → EARS → Tests → Code

For new features: create/update docs before writing code.
For bug fixes: verify existing docs align before changing code.

## Architecture

- **Frontend:** Next.js (TypeScript) on Vercel — `src/api/`, `src/components/`, `src/lib/`
- **Ingestion:** Python scripts — `src/ingestion/` (clients, scrapers, extractors)
- **Pipeline:** Python transforms — `src/pipeline/` (normalize, chunk, embed)
- **Database:** Supabase (Postgres + pgvector) — `supabase/migrations/`
- **CI/CD:** GitHub Actions — `.github/workflows/`

## Logic Flow Documentation

See **[`docs/LOGIC_FLOW.md`](docs/LOGIC_FLOW.md)** for the complete application logic flow with Mermaid diagrams and code snippets. **Update this document** whenever control flow, function signatures, data paths, or schema changes are made.

## Key Design Decisions

- **Model routing:** Simple queries → Gemini Flash (free); complex queries → Claude API (Sonnet)
- **Chunking:** Section-aware, not token-count based — legal text has natural boundaries
- **Data model:** Medallion architecture (Bronze raw → Silver normalized → Gold embeddings)
- **COMAR deferred:** State regulations excluded from MVP due to legal reuse restrictions

## Commands

```bash
# Frontend
npm run dev          # Next.js dev server
npm run build        # Production build
npm run lint         # ESLint

# Ingestion (Python)
python -m src.ingestion.clients.openstates    # Fetch state bills
python -m src.ingestion.scrapers.ecode360     # Scrape town code
python -m src.pipeline.normalize              # Bronze → Silver
python -m src.pipeline.embedder               # Silver → Gold

# Tests
npm test             # Frontend tests
pytest tests/        # Python tests
```

## Environment Variables

See `.env.example` for required variables. Never commit `.env.local`.

## Code Annotations

Use `@spec` comments to link code to EARS requirements:
```python
# @spec INGEST-API-001, INGEST-API-002
def fetch_state_bills():
    ...
```

```typescript
// @spec CHAT-RAG-001
export async function retrieveContext(query: string) { ... }
```

## File Conventions

- Python: snake_case files, type hints preferred, docstrings on public functions
- TypeScript: PascalCase components, camelCase utilities
- Tests mirror source structure: `src/ingestion/clients/openstates.py` → `tests/ingestion/test_openstates.py`
- Specs use semantic IDs: `{DOMAIN}-{TYPE}-{NNN}` (e.g., `INGEST-API-001`, `CHAT-RAG-003`)
