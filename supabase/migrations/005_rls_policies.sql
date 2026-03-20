-- CivicLens: Row Level Security policies
-- Migration: 005_rls_policies
-- Date: 2026-03-20
--
-- Security model:
--   anon role  — public frontend (NEXT_PUBLIC_SUPABASE_ANON_KEY)
--   service_role — ingestion pipeline and backend (SUPABASE_SERVICE_ROLE_KEY)
--
-- Public data: legislative_items, code_sections, document_chunks, meeting_records
--   → anon may SELECT only
-- Private data: bronze_documents, ingestion_runs, legiscan_dataset_hashes
--   → anon denied all access; service_role retains unrestricted access
--
-- @spec INFRA-SEC-001, INFRA-SEC-002, INFRA-SEC-003

-- ── Silver layer: public read ────────────────────────────────────────────────

alter table legislative_items enable row level security;

create policy "anon_read_legislative_items"
  on legislative_items
  for select
  to anon
  using (true);

alter table code_sections enable row level security;

create policy "anon_read_code_sections"
  on code_sections
  for select
  to anon
  using (true);

alter table meeting_records enable row level security;

create policy "anon_read_meeting_records"
  on meeting_records
  for select
  to anon
  using (true);

-- ── Gold layer: public read ──────────────────────────────────────────────────

alter table document_chunks enable row level security;

create policy "anon_read_document_chunks"
  on document_chunks
  for select
  to anon
  using (true);

-- ── Bronze / operational: deny anon, service_role retains full access ────────
-- (service_role bypasses RLS by default in Supabase; deny-all for anon only)

alter table bronze_documents enable row level security;
-- No SELECT policy for anon → anon is denied all access by default

alter table ingestion_runs enable row level security;
-- No SELECT policy for anon → anon is denied all access by default

alter table legiscan_dataset_hashes enable row level security;
-- No SELECT policy for anon → anon is denied all access by default
