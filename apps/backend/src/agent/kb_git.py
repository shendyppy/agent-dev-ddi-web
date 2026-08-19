"""Commit knowledge-base changes to git, so the corpus has a history.

Documents written through the web form used to exist only as files on the
server's disk. That meant no diff, no blame, no revert, no record of who wrote
what — and, on a container filesystem, no survival past the next deploy. One
commit per change buys all of those at once, which is why this is a small
module rather than a nice-to-have.

Deliberately non-fatal. A failure here is reported to the caller and logged,
but does not fail the request: the document is already validated, written and
indexed by that point, and refusing the whole save because the audit trail
could not be written would trade a working feature for a bookkeeping problem.
The response says plainly whether the commit happened, so "it saved but is not
in git" is never a silent state.
"""

from __future__ import annotations

import subprocess
import traceback
from pathlib import Path

# Generous, because a repo with a large working tree can take a moment to
# stage, but bounded so a wedged git (an index.lock left by a crashed editor,
# say) cannot hold the request open.
GIT_TIMEOUT_SECONDS = 30

# Used as the committer when the server has no git identity configured, which
# is the normal state for a service account. The *author* is always the person
# who submitted the document, so attribution survives regardless.
COMMITTER_NAME = "doc-agent"
COMMITTER_EMAIL = "doc-agent@localhost"


def commit_paths(
    repo_root: Path,
    paths: list[Path],
    message: str,
    author_email: str,
) -> str | None:
    """Stage ``paths`` and commit them. Returns the short SHA, or ``None``.

    ``None`` means "no commit was made" — git missing, not a repository,
    nothing actually changed, or a git error. All four are reported by the
    caller rather than raised, per the module docstring.

    The author is the submitter and the committer is the service, which is the
    same split git uses for patches applied on someone's behalf. ``git log
    --author`` therefore answers "what has this person documented?" directly.
    """
    if not paths:
        return None

    relative = [str(p.relative_to(repo_root)) if p.is_absolute() else str(p) for p in paths]

    try:
        _run(repo_root, ["add", "--", *relative])
        _run(
            repo_root,
            [
                "-c",
                f"user.name={COMMITTER_NAME}",
                "-c",
                f"user.email={COMMITTER_EMAIL}",
                "commit",
                f"--author={author_email} <{author_email}>",
                "-m",
                message,
                "--",
                *relative,
            ],
        )
        result = _run(repo_root, ["rev-parse", "--short", "HEAD"])
    except (OSError, subprocess.SubprocessError) as exc:
        # FileNotFoundError covers "git is not installed", which is a realistic
        # container state and must not take the save down with it.
        print(f"[kb-git] commit skipped: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return None

    return result.stdout.decode("utf-8", "replace").strip() or None


def _run(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Run one git command in ``repo_root``, raising on a non-zero exit."""
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        timeout=GIT_TIMEOUT_SECONDS,
    )
