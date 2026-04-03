/**
 * Rate limiting for POST /api/chat.
 *
 * Uses a Supabase table (rate_limits) to track per-IP request counts in
 * fixed 1-hour windows.  IP addresses are hashed before storage so no raw
 * client IPs are persisted.
 *
 * On database errors the check fails open — the request is allowed — so a
 * transient Supabase outage never blocks legitimate users.
 *
 * Configuration:
 *   CHAT_RATE_LIMIT   — max requests per IP per hour (default: 50)
 *
 * @spec CHAT-RLMT-001, CHAT-RLMT-002, CHAT-RLMT-003, CHAT-RLMT-004
 */

import { NextRequest } from "next/server";
import { createServerClient } from "@/lib/supabase-client";

/** Maximum requests allowed per IP per hour. */
const RATE_LIMIT = parseInt(process.env.CHAT_RATE_LIMIT ?? "50", 10);

export interface RateLimitResult {
  allowed: boolean;
  limit: number;
  remaining: number;
  /** Unix timestamp (seconds) when the current window resets. */
  resetAt: number;
}

/**
 * Returns the start of the current fixed 1-hour window (minutes/seconds
 * truncated to zero).
 */
function currentWindowStart(): Date {
  const now = new Date();
  now.setMinutes(0, 0, 0);
  return now;
}

/**
 * Extracts the client IP from request headers.
 * Prefers X-Forwarded-For (set by Vercel edge) over X-Real-IP.
 */
export function getClientIp(request: NextRequest): string {
  return (
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    request.headers.get("x-real-ip") ??
    "unknown"
  );
}

/**
 * Returns a deterministic integer hash of the IP string.
 * Not cryptographic — used only to avoid storing raw IPs.
 */
function hashIp(ip: string): string {
  let h = 0;
  for (let i = 0; i < ip.length; i++) {
    h = (Math.imul(31, h) + ip.charCodeAt(i)) | 0;
  }
  return (h >>> 0).toString(36);
}

/**
 * Checks and increments the rate limit counter for the requesting IP.
 *
 * Returns `allowed: false` when the caller has exceeded `RATE_LIMIT`
 * requests in the current hour.  On Supabase errors, fails open.
 *
 * @spec CHAT-RLMT-001
 */
export async function checkRateLimit(
  request: NextRequest
): Promise<RateLimitResult> {
  const windowStart = currentWindowStart();
  const resetAt = Math.floor(
    (windowStart.getTime() + 60 * 60 * 1000) / 1000
  );

  const ipHash = hashIp(getClientIp(request));
  const db = createServerClient();

  const { data, error } = await db.rpc("increment_rate_limit", {
    p_ip_hash: ipHash,
    p_window_start: windowStart.toISOString(),
  });

  if (error) {
    // Fail open: allow the request if the rate-limit check itself errors.
    console.error("Rate limit check error:", error.message);
    return { allowed: true, limit: RATE_LIMIT, remaining: RATE_LIMIT, resetAt };
  }

  const count = (data as number) ?? 1;
  const allowed = count <= RATE_LIMIT;
  const remaining = Math.max(0, RATE_LIMIT - count);

  return { allowed, limit: RATE_LIMIT, remaining, resetAt };
}
