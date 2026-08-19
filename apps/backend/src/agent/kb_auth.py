"""Who is allowed to write documentation, and how we know it is them.

Before this module, ``POST /api/knowledge-base`` was unauthenticated. The
frontend only rendered the button behind ``user &&``, which is a rendering
decision, not a security one — the endpoint accepted an anonymous curl from
anyone who could reach the port, and wrote whatever it was given straight into
the corpus the agent answers from.

Verification goes through Supabase's own ``/auth/v1/user`` endpoint rather than
local JWT signature checking. That trades a network round trip (on a request
that already writes a file, so it is not the expensive part) for not needing
the project's JWT secret in ``.env`` at all — one fewer secret to distribute,
rotate, and leak. It also means a revoked session stops working immediately
instead of at token expiry.

Two levels, because two is what the workflow actually has:

- **submitting** is open to any signed-in user. Documents land in the review
  inbox and are not searchable until published, so the cost of a bad one is a
  file nobody reads yet. Gating it would only deter contribution.
- **publishing** puts a document in front of every user of the agent, so it
  needs an explicit grant — a row in the ``kb_roles`` table (see
  ``kb_roles.py`` and ``supabase/migrations/``), or the bootstrap list in
  ``KB_MAINTAINER_EMAILS`` for the first maintainer on an empty database.

Roles used to be two env vars. That was wrong: a list of people is data, not
configuration, and keeping it in ``.env`` meant granting access required a
server edit and a restart.
"""

from __future__ import annotations

import httpx
from fastapi import Header, HTTPException

from .kb_roles import fetch_role
from .settings import settings

# Supabase is not fast, but it is not slow either, and a save is a rare,
# deliberate action. Long enough to survive a cold edge function, short enough
# that a hung auth service does not hold a threadpool worker for a minute.
AUTH_TIMEOUT_SECONDS = 10.0


async def _resolve_identity(authorization: str | None) -> tuple[str, str]:
    """``(email, token)`` behind a bearer header, or raise 401/503.

    The token is returned alongside the email because the role lookup reuses
    it: ``kb_roles`` grants "read your own row" to the caller, so their own
    credential is enough and no service-role key has to exist.

    Email comes back lowercased — it is used for allowlist comparison, for the
    role lookup, and for the git commit author, none of which should care about
    the casing a provider happened to hand back.
    """
    if not settings.supabase_url or not settings.supabase_anon_key:
        # Fail closed. An unconfigured auth backend must not silently become
        # "no auth required" — that is exactly the state this module exists to
        # end.
        raise HTTPException(
            status_code=503,
            detail=(
                "authentication is not configured on this server "
                "(PUBLIC_SUPABASE_URL / PUBLIC_SUPABASE_ANON_KEY are unset), "
                "so documents cannot be accepted."
            ),
        )

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="sign in first: this endpoint needs an Authorization: Bearer <token> header.",
        )

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="empty bearer token.")

    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/user"
    try:
        async with httpx.AsyncClient(timeout=AUTH_TIMEOUT_SECONDS) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}", "apikey": settings.supabase_anon_key},
            )
    except httpx.HTTPError as exc:
        # Transient by nature — say so, rather than reporting it as a rejected
        # identity, which would send the user off to re-authenticate for no
        # reason.
        raise HTTPException(
            status_code=503,
            detail=f"could not reach the authentication service: {type(exc).__name__}",
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=401, detail="session is invalid or expired — sign in again."
        )

    email = (response.json() or {}).get("email")
    if not email:
        raise HTTPException(
            status_code=403,
            detail=(
                "this account has no email address, so it cannot be recorded as a document owner."
            ),
        )
    return str(email).strip().lower(), token


def _is_bootstrap_maintainer(email: str) -> bool:
    """Membership test supporting both full emails and ``@domain`` suffixes.

    An EMPTY list matches nobody — the opposite of the old writer allowlist,
    and deliberately so. This is a seed for the first maintainer, not a switch
    that turns publishing into a free-for-all when left unconfigured.
    """
    return any(
        email == entry if not entry.startswith("@") else email.endswith(entry)
        for entry in settings.kb_maintainer_list
    )


async def require_kb_writer(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: verified email of someone allowed to submit docs.

    No role required. A submission is quarantined in the review inbox and
    cannot be answered from until a maintainer publishes it, so the gate that
    matters is the one on publishing.
    """
    email, _token = await _resolve_identity(authorization)
    return email


async def require_kb_maintainer(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: verified email of someone allowed to publish docs."""
    email, token = await _resolve_identity(authorization)

    # Bootstrap first, so this still works against a database where the
    # kb_roles table does not exist yet.
    if _is_bootstrap_maintainer(email):
        return email

    if await fetch_role(email, token) == "maintainer":
        return email

    raise HTTPException(
        status_code=403,
        detail=(
            f"{email} cannot publish documents. Ask a maintainer to grant the role "
            "(see supabase/README.md); submitting for review needs no extra access."
        ),
    )
