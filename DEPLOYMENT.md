# Deployment Guide

This guide covers deploying CivicLens for public access. The full stack is free-tier eligible: Supabase (database), Vercel (hosting), and GitHub Actions (ingestion).

**Estimated setup time:** 30–60 minutes.

---

## Prerequisites

- GitHub account with this repo forked or cloned
- Node.js 20+ and Python 3.11+ installed locally
- Accounts (all free): [Supabase](https://supabase.com), [Vercel](https://vercel.com)
- API keys (see [API Key Procurement](#api-key-procurement))

---

## 1. Supabase Setup

### 1.1 Create the project

1. Go to [supabase.com/dashboard](https://supabase.com/dashboard) → **New project**
2. Set a strong database password and save it — you'll need it if you ever use the Supabase CLI
3. Choose the **US East** region (closest to Bel Air, MD)
4. Wait for provisioning (~2 minutes)

### 1.2 Enable pgvector

1. In your project, go to **Database → Extensions**
2. Search for `vector` and enable it
3. Confirm the extension is listed as enabled

### 1.3 Run migrations

Apply schema migrations in order from `supabase/migrations/`:

**Option A — Supabase Dashboard (easiest for first deploy):**
1. Go to **SQL Editor** in your Supabase project
2. Open and run each migration file in order: `001_initial_schema.sql`, `002_vector_search_rpc.sql`, etc.

**Option B — Supabase CLI:**
```bash
npm install -g supabase
supabase login
supabase link --project-ref YOUR_PROJECT_REF
supabase db push
```
Your project ref is in the Supabase dashboard URL: `supabase.com/dashboard/project/YOUR_PROJECT_REF`.

### 1.4 Collect credentials

From **Project Settings → API**, copy:
- **Project URL** → `NEXT_PUBLIC_SUPABASE_URL`
- **anon public key** → `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- **service_role secret key** → `SUPABASE_SERVICE_ROLE_KEY`

> **Security note:** The `service_role` key bypasses row-level security. Never expose it in client-side code or commit it to the repo.

---

## 2. Vercel Deployment

### 2.1 Import the project

1. Go to [vercel.com/new](https://vercel.com/new)
2. Click **Import Git Repository** and select your fork
3. Vercel auto-detects Next.js — leave the build settings as-is
4. Do **not** deploy yet — configure environment variables first

### 2.2 Set environment variables

In the Vercel project settings → **Environment Variables**, add all variables from `.env.example`:

| Variable | Where to get it |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase → Project Settings → API |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase → Project Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `GOOGLE_AI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `OPENSTATES_API_KEY` | [openstates.org/accounts/signup](https://openstates.org/accounts/signup/) |
| `LEGISCAN_API_KEY` | [legiscan.com/user/register](https://legiscan.com/user/register) |
| `MODEL_ROUTING_DOC_THRESHOLD` | Set to `3` |
| `RAG_TOP_K` | Set to `8` |
| `EMBEDDING_MODEL` | Set to `gemini` |

Set the **Environment** to **Production, Preview, and Development** for all variables.

### 2.3 Deploy

Click **Deploy**. Vercel will build and publish the app. The deployment URL will be something like `civiclens.vercel.app`.

On every subsequent `git push` to `main`, Vercel automatically redeploys.

### 2.4 Custom domain (optional)

In Vercel → **Domains**, add your own domain and follow the DNS instructions. Vercel provisions HTTPS automatically.

---

## 3. GitHub Actions (Ingestion Pipeline)

The ingestion pipeline runs on a schedule via GitHub Actions. It fetches legislative data and keeps the database current.

### 3.1 Add repository secrets

In your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**, add:

| Secret | Value |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Your service role key |
| `OPENSTATES_API_KEY` | Open States API key |
| `LEGISCAN_API_KEY` | LegiScan API key |
| `GOOGLE_AI_API_KEY` | Google AI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key (for any enrichment steps) |

### 3.2 Enable workflows

1. Go to **Actions** tab in your GitHub repo
2. If prompted, click **I understand my workflows, go ahead and enable them**
3. The `ingest.yml` workflow will run on its configured schedule automatically

### 3.3 Run ingestion manually (first time)

On first deploy the database is empty. Trigger a manual run to populate it:

1. Go to **Actions → Ingest** workflow
2. Click **Run workflow** → **Run workflow**
3. Watch the job logs — each stage (ingest → normalize → embed) should complete with green checks

Alternatively, run ingestion locally before deploying:
```bash
pip install -r requirements.txt
cp .env.example .env.local
# Fill in .env.local with your keys

python -m src.ingestion.clients.openstates
python -m src.ingestion.scrapers.ecode360
python -m src.pipeline.normalize
python -m src.pipeline.embedder
```

---

## 4. Verify the Deployment

Once all three services are configured:

1. **Database:** In Supabase → Table Editor, confirm rows appear in the Silver tables (`legislative_items`, `code_sections`) after ingestion
2. **Chat:** Open `https://your-app.vercel.app/chat` and ask a question — e.g., *"What are the noise ordinances in Bel Air?"*
3. **Dashboard:** Open `/` and confirm legislative items are listed

If the chat returns no results, ingestion likely hasn't run yet or embeddings are missing — trigger a manual workflow run.

---

## 5. Sharing the Test URL

The Vercel deployment URL is publicly accessible immediately. Share it as-is for testing:

```
https://YOUR_PROJECT.vercel.app
```

> **Note:** The app is read-only for visitors. All writes go through the `service_role` key in GitHub Actions and Vercel server functions — never exposed to the browser.

For preview deployments on feature branches, Vercel auto-generates a unique URL per push (e.g., `civiclens-git-feature-branch-yourname.vercel.app`). These are useful for testing before merging.

---

## API Key Procurement

All required keys are free for MVP usage:

| Service | URL | Free tier |
|---|---|---|
| Open States | [openstates.org/accounts/signup](https://openstates.org/accounts/signup/) | Unlimited (rate-limited) |
| LegiScan | [legiscan.com/user/register](https://legiscan.com/user/register) | 30,000 queries/month |
| Google AI (Gemini) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | 1,500 embedding requests/day |
| Anthropic (Claude) | [console.anthropic.com](https://console.anthropic.com) | Pay-per-use (~$0–10/month at MVP scale) |
| Supabase | [supabase.com](https://supabase.com) | Free tier (500MB DB, 1GB storage) |
| Vercel | [vercel.com](https://vercel.com) | Free Hobby plan |

---

## Troubleshooting

**Build fails on Vercel with missing env vars**
Ensure all variables from `.env.example` are set in the Vercel dashboard. Variables prefixed `NEXT_PUBLIC_` must be set for the build to succeed.

**Chat returns empty results**
Run ingestion manually (see §3.3). Confirm rows exist in `document_chunks` table and the `embedding` column is populated.

**pgvector extension errors**
The `vector` extension must be enabled before running migrations. Re-run the `001_initial_schema.sql` migration after enabling it.

**GitHub Actions failing with auth errors**
Double-check that the secret names match exactly (they're case-sensitive). `SUPABASE_URL` not `NEXT_PUBLIC_SUPABASE_URL` — the GitHub Actions workflow uses server-side env var names.

**Vercel serverless timeout on chat**
The free tier has a 10-second function timeout. If complex Claude API calls are timing out, enable streaming responses in the `/api/chat` route (returns chunks as they arrive, resetting the timeout clock).
