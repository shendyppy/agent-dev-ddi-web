/**
 * Supabase client — auth + chat history. OPTIONAL.
 *
 * This used to be `createClient(url, key)` with both values read straight from
 * `import.meta.env`. When they were absent — no `.env`, or a `.env` the dev
 * server could not find — `createClient` threw `supabaseUrl is required` at
 * module load. That happens during island hydration, so the exception took the
 * entire Chat component down and the page rendered blank, with the real cause
 * visible only in the browser console.
 *
 * Auth and history are enhancements: the chatbot answers questions perfectly
 * well without either. A missing optional credential must therefore degrade to
 * "sign-in is unavailable", never to "the app is gone".
 *
 * So the client is `null` when unconfigured and every caller checks. Callers
 * that skip the check get a TypeScript error rather than a runtime blank page.
 */
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const url = import.meta.env.PUBLIC_SUPABASE_URL as string | undefined;
const key = import.meta.env.PUBLIC_SUPABASE_ANON_KEY as string | undefined;

/** True when both values are present, so the UI can hide sign-in rather than
 *  offering a button that cannot work. */
export const isSupabaseConfigured = Boolean(url && key);

export const supabase: SupabaseClient | null = isSupabaseConfigured
  ? createClient(url as string, key as string)
  : null;

if (!isSupabaseConfigured && import.meta.env.DEV) {
  // Dev only, and worth saying out loud: silence here would look like the
  // sign-in button simply not existing.
  console.info(
    '[supabase] PUBLIC_SUPABASE_URL / PUBLIC_SUPABASE_ANON_KEY not set — ' +
      'sign-in and chat history are disabled. Chat itself works normally.',
  );
}
