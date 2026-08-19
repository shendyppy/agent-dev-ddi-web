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

Two roles, because two is what the workflow actually has:

- **writer** — may submit a document. It lands in the review inbox.
- **maintainer** — may publish a document out of the inbox into the corpus.

Anything finer than that would be role-modelling for its own sake on a team
this size.
"""

from __future__ import annotations

import httpx
from fastapi import Header, HTTPException

from .settings import settings

# Supabase is not fast, but it is not slow either, and a save is a rare,
# deliberate action. Long enough to survive a cold edge function, short enough
# that a hung auth service does not hold a threadpool worker for a minute.
AUTH_TIMEOUT_SECONDS = 10.0


async def _resolve_email(authorization: str | None) -> str:
    """The verified email behind a bearer token, or raise 401/503.

    Returns the email lowercased, because it is used for allowlist comparison
    and for the git commit trailer — both of which should not care about the
    casing a provider happened to hand back.
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
    return str(email).strip().lower()


def _is_allowed(email: str, allowlist: list[str]) -> bool:
    """Membership test supporting both full emails and ``@domain`` suffixes.

    An empty allowlist admits everyone who got this far — and getting this far
    already required a verified session.
    """
    if not allowlist:
        return True
    return any(
        email == entry if not entry.startswith("@") else email.endswith(entry)
        for entry in allowlist
    )


async def require_kb_writer(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: verified email of someone allowed to submit docs."""
    email = await _resolve_email(authorization)
    if not _is_allowed(email, settings.kb_writer_list):
        raise HTTPException(
            status_code=403,
            detail=f"{email} is not on KB_WRITER_EMAILS, so it cannot add documentation.",
        )
    return email


async def require_kb_maintainer(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: verified email of someone allowed to publish docs."""
    email = await _resolve_email(authorization)
    if not _is_allowed(email, settings.kb_maintainer_list):
        raise HTTPException(
            status_code=403,
            detail=(
                f"{email} is not on KB_MAINTAINER_EMAILS, so it cannot publish "
                "documents out of the review inbox."
            ),
        )
    return email
