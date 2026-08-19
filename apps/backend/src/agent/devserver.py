"""Resolve the TCP port the dev backend should bind, before anything starts.

``just dev`` used to hardcode ``--port 8000``. When another service already
held that port, uvicorn exited with ``[Errno 10048]`` while ``concurrently``
kept the frontend running — so the browser went on talking to whatever foreign
service owned 8000. That service answered ``/api/products`` with 404 and,
because its own CORS allowlist did not contain our origin, without an
``Access-Control-Allow-Origin`` header. The browser therefore reported a CORS
failure, the 404 underneath was never visible to JS, and an environment
collision looked exactly like a code regression.

Resolving the port up front and handing the same value to both halves removes
the assumption: ``just dev`` runs this module, exports the result as
``BACKEND_PORT`` and ``PUBLIC_API_BASE_URL``, and frontend and backend agree by
construction rather than by coincidence.
"""

from __future__ import annotations

import argparse
import socket

from .settings import settings

# How far above the preferred port to look before giving up. Wide enough to
# step over a handful of other local services, narrow enough that a genuinely
# wedged machine fails loudly instead of binding something surprising.
PORT_SCAN_SPAN = 20


def is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    """True when nothing is listening on ``host:port``.

    Binds rather than connects. A connect probe cannot tell "nothing is
    listening" apart from "something is listening but refused us", and binding
    is what uvicorn has to do later anyway — so this fails in exactly the cases
    uvicorn would.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # Deliberately no SO_REUSEADDR: it would let this probe succeed on a
        # port a live listener still owns, which is the whole failure we are
        # trying to detect.
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def resolve_port(
    preferred: int | None = None,
    host: str = "127.0.0.1",
    span: int = PORT_SCAN_SPAN,
) -> int:
    """First free port at or above ``preferred``.

    Returns ``preferred`` untouched whenever it is available, so the ordinary
    case stays at the ordinary port and nobody's bookmarks move. Only a
    collision causes a shift.
    """
    start = settings.backend_port if preferred is None else preferred
    for port in range(start, start + span):
        if is_port_free(port, host):
            return port
    raise RuntimeError(
        f"no free TCP port in {start}..{start + span - 1} on {host}. "
        "Stop whatever is holding that range, or set BACKEND_PORT elsewhere."
    )


def main() -> None:
    """Print the resolved port. ``just dev`` captures stdout, so print nothing else."""
    parser = argparse.ArgumentParser(description="Resolve a free port for the dev backend.")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="preferred port (default: BACKEND_PORT from settings)",
    )
    args = parser.parse_args()
    print(resolve_port(args.port))


if __name__ == "__main__":
    main()
