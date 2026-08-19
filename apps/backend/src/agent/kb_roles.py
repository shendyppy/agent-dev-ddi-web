"""Look up a caller's knowledge-base role in Supabase.

Roles used to live in ``KB_WRITER_EMAILS`` / ``KB_MAINTAINER_EMAILS``. That was
the wrong home: a list of people changes when somebody joins or leaves, not
when we deploy, so granting access meant editing a file on the server and
restarting the backend — and left no record of who granted what, in a second
place describing people next to the Supabase tables that already do.

The lookup reuses the CALLER'S OWN token rather than a service-role key. That
matters: adding a service-role key to ``.env`` would put a credential that
bypasses every RLS policy in the project next to an anon key that bypasses
none, to answer a question the caller is already allowed to ask about
themselves. The ``kb_roles`` policy grants exactly "read your own row", so this
query works with the token we already verified and nothing more.

See ``supabase/migrations/20260819120000_kb_roles.sql`` and ADR 0011.
"""

from __future__ import annotations

import httpx

from .settings import settings

# Same budget as the token check in kb_auth — one more small round trip on a
# request that is about to write a file and re-embed a document.
ROLE_TIMEOUT_SECONDS = 10.0


async def fetch_role(email: str, token: str) -> str | None:
    """The caller's row in ``kb_roles``, or ``None``.

    ``None`` covers every "no answer" case — no row, RLS refused, the table has
    not been created yet, Supabase unreachable — because callers treat them
    identically: fall back to the bootstrap list, then to the default. A
    lookup failure must not hand out a role, and must not take down submission
    either, since submitting needs no role at all.
    """
    if not settings.supabase_url or not settings.supabase_anon_key:
        return None

    url = f"{settings.supabase_url.rstrip('/')}/rest/v1/kb_roles"
    try:
        async with httpx.AsyncClient(timeout=ROLE_TIMEOUT_SECONDS) as client:
            response = await client.get(
                url,
                params={"email": f"eq.{email.lower()}", "select": "role", "limit": 1},
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": settings.supabase_anon_key,
                },
            )
    except httpx.HTTPError:
        # Deliberately quiet: this is a fallback path, and a maintainer being
        # asked to retry is a better outcome than a 500 on a document that is
        # otherwise fine.
        return None

    if response.status_code != 200:
        # 404 when the migration has not been applied yet; 401/403 if the policy
        # is missing. Both mean "no role known", not "error".
        return None

    try:
        rows = response.json()
    except ValueError:
        return None

    if not isinstance(rows, list) or not rows:
        return None

    role = rows[0].get("role")
    return str(role).strip().lower() if role else None
