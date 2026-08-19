# Supabase schema

SQL for the tables this app relies on. Apply a migration by pasting it into the
Supabase dashboard SQL editor, or with the CLI if you have it linked:

```bash
supabase db push
```

## What is and is not in here

`migrations/` currently covers **only `kb_roles`**. The chat tables
(`chat_sessions`, `chat_messages`, added in PR #8) were created by hand in the
dashboard and were never captured as SQL, so this folder cannot yet rebuild the
project from scratch.

That is worth fixing, and the reason to start here rather than to wait: schema
that lives only in a dashboard has no history, no review, and no way for a
second contributor to reproduce it. Dumping the existing two tables into a
`00000_baseline.sql` is the obvious next step — done from the real project so
it matches reality instead of someone's memory of it.

## Granting publish rights

Submitting a document is open to any signed-in user; submissions are quarantined
in `docs/knowledge-base/_inbox/` until reviewed. **Publishing** needs a row:

```sql
insert into public.kb_roles (email, role, granted_by)
values ('budi@company.com', 'maintainer', 'shendyppy@gmail.com')
on conflict (email) do update set role = excluded.role;
```

No restart needed — the backend reads this per request.

`kb_roles` has RLS on with only a "read your own row" policy, so inserts have to
come from the dashboard or the service-role key. That is deliberate: granting
publish rights should take more than a click in the app.

### Bootstrapping the first maintainer

Chicken and egg: the first grant has to come from somewhere. Set
`KB_MAINTAINER_EMAILS` in `.env` to seed it — that list is checked *before*
this table, so it works on an empty database. Keep it to the one or two people
who administer the deployment, and grant everyone else a row here.

See [ADR 0011](../docs/adr/0011-knowledge-base-write-path.md).
