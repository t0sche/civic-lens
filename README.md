# CivicLens

**Plain-language access to the laws that affect you.**

CivicLens is a civic transparency platform for Bel Air, Maryland (21015). It combines a RAG-powered chat interface with a legislative tracking dashboard to make government data across three jurisdictions — Maryland State, Harford County, and the Town of Bel Air — accessible to residents without legal training or government website expertise.

## Status

🚧 **Pre-alpha** — Architecture defined, implementation not yet started. See `docs/` for design documents.

## Architecture

```
Data Sources → Ingestion (Python/GitHub Actions) → Supabase (Bronze/Silver/Gold)
                                                          ↓
                                              ┌───────────┴───────────┐
                                              ▼                       ▼
                                         Chat (RAG)            Dashboard (SSR)
                                              └───────────┬───────────┘
                                                    Next.js / Vercel
```

**Data sources:** Open States API, LegiScan API, eCode360 (county/town codes), CivicPlus (agendas/minutes), Harford County bills tracker, Bel Air legislation page.

**Stack:** Next.js (Vercel), Supabase (Postgres + pgvector), Python (ingestion), Claude API + Gemini Flash (model routing).

## Project Structure

```
civiclens/
├── docs/                    # Design-driven development docs
│   ├── high-level-design.md # Project vision and architecture
│   ├── arrows/              # Arrow of intent tracking
│   │   ├── index.yaml       # Dependency graph and status
│   │   └── *.md             # Per-domain arrow docs
│   ├── llds/                # Low-level designs (per component)
│   ├── specs/               # EARS specifications
│   └── planning/            # Implementation plans
├── src/
│   ├── ingestion/           # Python data collection
│   │   ├── clients/         # API clients (Open States, LegiScan, etc.)
│   │   ├── scrapers/        # HTML scrapers (eCode360, CivicPlus, etc.)
│   │   └── extractors/      # PDF text extraction
│   ├── pipeline/            # Bronze → Silver → Gold transforms
│   ├── api/                 # Next.js API routes
│   ├── components/          # React components
│   └── lib/                 # Shared utilities (Supabase client, RAG, etc.)
├── supabase/
│   └── migrations/          # Database schema migrations
├── scripts/                 # One-off and utility scripts
├── tests/                   # Test suites mirroring src/ structure
├── .github/workflows/       # GitHub Actions for ingestion cron
└── CLAUDE.md                # Instructions for Claude Code sessions
```

## Getting Started

### Prerequisites

- Node.js 20+
- Python 3.11+
- Supabase account (free tier)
- API keys: Open States, LegiScan, Anthropic (Claude), Google AI (Gemini)

### Setup

```bash
# Clone and install
git clone https://github.com/YOUR_USERNAME/civiclens.git
cd civiclens
npm install

# Python ingestion dependencies
pip install -r requirements.txt

# Environment variables
cp .env.example .env.local
# Edit .env.local with your API keys

# Run Next.js dev server
npm run dev

# Run ingestion (one-time)
python -m src.ingestion.clients.openstates
```

## Design Documents

This project follows a [design-driven development](docs/high-level-design.md) workflow with full traceability from requirements to code.

Start with `docs/arrows/index.yaml` to understand the project map, then read `docs/high-level-design.md` for the full architecture.

## License

MIT — civic data should be accessible.
