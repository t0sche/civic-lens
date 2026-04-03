-- CivicLens: Rate limiting for /api/chat
-- Migration: 005_rate_limits
-- Date: 2026-03-20
--
-- Tracks per-IP request counts in fixed 1-hour windows so the chat endpoint
-- can reject requests that exceed the configured limit, preventing runaway
-- API costs.  IP addresses are stored as deterministic hashes; raw IPs are
-- never persisted.
--
-- @spec CHAT-RLMT-001, CHAT-RLMT-002, CHAT-RLMT-003

-- ═══════════════════════════════════════════════════════════════════════
-- RATE LIMITS TABLE
-- ═══════════════════════════════════════════════════════════════════════

create table if not exists rate_limits (
    ip_hash       text        not null,   -- deterministic hash of client IP
    window_start  timestamptz not null,   -- start of the 1-hour fixed window
    request_count integer     not null default 1,
    primary key (ip_hash, window_start)
);

-- Index used by the cleanup query and the window look-up in the RPC.
create index if not exists idx_rate_limits_window
    on rate_limits(window_start);

-- ═══════════════════════════════════════════════════════════════════════
-- ATOMIC INCREMENT RPC
-- ═══════════════════════════════════════════════════════════════════════
-- Inserts a new row for (ip_hash, window_start), or increments request_count
-- when a row already exists.  Returns the updated count so the caller can
-- decide whether to allow or reject the request.

create or replace function increment_rate_limit(
    p_ip_hash      text,
    p_window_start timestamptz
)
returns integer
language plpgsql
security definer
as $$
declare
    v_count integer;
begin
    insert into rate_limits (ip_hash, window_start, request_count)
    values (p_ip_hash, p_window_start, 1)
    on conflict (ip_hash, window_start)
    do update set request_count = rate_limits.request_count + 1
    returning request_count into v_count;

    return v_count;
end;
$$;

-- ═══════════════════════════════════════════════════════════════════════
-- CLEANUP RPC
-- ═══════════════════════════════════════════════════════════════════════
-- Removes windows older than 2 hours.  Call periodically (e.g. from a
-- Supabase cron job or ingestion workflow) to keep the table small.

create or replace function purge_old_rate_limit_windows()
returns void
language sql
security definer
as $$
    delete from rate_limits
    where window_start < now() - interval '2 hours';
$$;
