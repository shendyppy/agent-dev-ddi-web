-- Who may publish knowledge-base documents.
--
-- This replaces a KB_WRITER_EMAILS / KB_MAINTAINER_EMAILS pair in .env. An
-- allowlist of people is data, not configuration: it changes when somebody
-- joins or leaves, not when we deploy. Keeping it in .env meant "give Budi
-- access" required editing a file on the server and restarting the backend,
-- and left no record of who granted what. It also described people in a second
-- place, next to the Supabase auth tables that already do.
--
-- The model is deliberately small:
--   * submitting is open to any signed-in user — submissions land in
--     docs/knowledge-base/_inbox/ and are not searchable until reviewed, so the
--     blast radius of a bad one is a file nobody reads yet.
--   * publishing is the action with consequences, so it needs a row here.
--
-- KB_MAINTAINER_EMAILS survives in .env as a BOOTSTRAP seed only: somebody has
-- to be able to grant the first role before there is any way to grant roles.

create table if not exists public.kb_roles (
  -- Email rather than a user_id FK: roles are usually granted to a colleague
  -- before their first sign-in, and a uuid does not exist until then. Stored
  -- lowercase (see the check) because that is how the backend compares it.
  email text primary key check (email = lower(email)),
  role text not null check (role in ('writer', 'maintainer')),
  -- Who granted it. Free text, filled by whoever inserts the row — the audit
  -- trail this whole change exists to create.
  granted_by text,
  created_at timestamptz not null default now()
);

comment on table public.kb_roles is
  'Knowledge-base permissions. See docs/adr/0011-knowledge-base-write-path.md.';

alter table public.kb_roles enable row level security;

-- A signed-in user may read their OWN role and nothing else. That is all the
-- backend needs: it looks up the caller, never the whole table. Listing every
-- grant is an admin concern and gets its own policy the day an admin UI exists.
drop policy if exists "kb_roles: read own role" on public.kb_roles;
create policy "kb_roles: read own role"
  on public.kb_roles
  for select
  to authenticated
  using (email = lower(auth.jwt() ->> 'email'));

-- No insert/update/delete policy on purpose. With RLS enabled and no policy,
-- those are denied for anon and authenticated clients, so grants can only be
-- made from the Supabase dashboard or with the service-role key — which is
-- exactly the level of ceremony granting publish rights should have.
