# Infrastructure Specifications

**Design Doc**: `/docs/llds/infrastructure.md`
**Arrow**: `/docs/arrows/infrastructure.md`

## Database Schema

- [ ] **INFRA-DB-001**: The system shall provide a `bronze_documents` table with columns: id (UUID PK), source, source_id, document_type, raw_content, raw_metadata (JSONB), url, fetched_at, content_hash, with a unique constraint on (source, source_id).
- [ ] **INFRA-DB-002**: The system shall provide a `legislative_items` table matching the Silver layer schema defined in HLD §7, with indexes on jurisdiction, status, item_type, last_action_date, and tags (GIN).
- [ ] **INFRA-DB-003**: The system shall provide a `code_sections` table matching the Silver layer schema defined in HLD §7, with indexes on jurisdiction, code_source, and chapter.
- [ ] **INFRA-DB-004**: The system shall provide a `meeting_records` table matching the Silver layer schema defined in HLD §7, with indexes on jurisdiction, body, and meeting_date.
- [ ] **INFRA-DB-005**: The system shall provide a `document_chunks` table with a `vector(768)` embedding column and an HNSW index using `vector_cosine_ops` with m=16 and ef_construction=64.
- [ ] **INFRA-DB-006**: The system shall provide an `ingestion_runs` table that tracks source, started_at, completed_at, status, records_fetched, records_new, records_updated, and error_message.
- [ ] **INFRA-DB-007**: When a row in legislative_items, code_sections, or meeting_records is updated, the system shall automatically set updated_at to the current timestamp via a database trigger.
- [ ] **INFRA-DB-008**: The system shall provide a `match_document_chunks` RPC function that accepts a query embedding, similarity threshold, match count, and optional jurisdiction filter, and returns matching chunks ordered by descending cosine similarity.

## Database Security

- [ ] **INFRA-SEC-001**: The system shall allow the `anon` role SELECT access to legislative_items, code_sections, meeting_records, and document_chunks.
- [ ] **INFRA-SEC-002**: The system shall restrict INSERT, UPDATE, and DELETE on all tables to the `service_role` key only.
- [ ] **INFRA-SEC-003**: The system shall restrict all access to ingestion_runs to the `service_role` key only.

## Environment Configuration

- [ ] **INFRA-ENV-001**: The system shall load configuration from environment variables, with `.env.local` support for local development via python-dotenv.
- [ ] **INFRA-ENV-002**: The system shall require NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY for all database operations.
- [ ] **INFRA-ENV-003**: If a required environment variable is missing, then the system shall raise an error with a clear message identifying the missing variable.
- [ ] **INFRA-ENV-004**: The system shall provide an `.env.example` file documenting all required and optional environment variables with descriptions.

## CI/CD Pipeline

- [ ] **INFRA-CI-001**: The system shall run state bill ingestion (Open States) every 6 hours via a GitHub Actions cron schedule.
- [ ] **INFRA-CI-002**: The system shall run local data scraping (eCode360, Bel Air legislation) daily at 6:00 AM Eastern via a GitHub Actions cron schedule.
- [ ] **INFRA-CI-003**: When ingestion jobs complete successfully, the system shall run Bronze→Silver normalization followed by embedding generation.
- [ ] **INFRA-CI-004**: If any ingestion or pipeline job fails, then the system shall log the failure with job-specific status in the GitHub Actions output.
- [ ] **INFRA-CI-005**: The system shall support manual workflow dispatch with a source selector (openstates, legiscan, ecode360, belair, all) and a skip-embeddings flag.

## Supabase Client

- [ ] **INFRA-CLIENT-001**: The system shall provide a Python function `get_supabase_client()` that returns an authenticated Supabase client using the service role key.
- [ ] **INFRA-CLIENT-002**: The system shall provide a TypeScript function `createServerClient()` that returns an authenticated Supabase client using the service role key for server-side use.
- [ ] **INFRA-CLIENT-003**: The system shall provide a TypeScript function `createBrowserClient()` that returns a Supabase client using the anon key for client-side use.
