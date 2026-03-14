import { createClient } from "@supabase/supabase-js";

/**
 * Browser-side Supabase client using the anon key.
 * Used by client components for real-time subscriptions and public queries.
 */
export function createBrowserClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}

/**
 * Server-side Supabase client using the service role key.
 * Used by API routes and server components for privileged access.
 */
export function createServerClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );
}
