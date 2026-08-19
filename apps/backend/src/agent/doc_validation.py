"""One validator for knowledge-base documents, shared by the API and by CI.

``docs/PRODUCT-DOC-FORMAT.md`` has listed ``just validate-docs`` as a TODO
since ADR 0006, with the note "until that runs in CI, treat this spec as a
code-review checklist". That was survivable while documents were written by
hand in an editor. It stopped being survivable when the web form landed: a
form produces invalid documents faster than a human reviewer can catch them,
and the corpus has no other gate.

The point of putting the checks *here* rather than inside the endpoint is that
there is exactly one definition of "valid". :func:`validate_document` runs
pre-write so a bad document is refused with a 422 and never reaches disk, and
the same function runs over the whole corpus from ``just validate-docs`` so a
document that rotted after it was written still gets caught. Two consumers,
one implementation — a second copy would drift and the drift would be silent.

What is deliberately NOT checked here: the full per-product spec in
PRODUCT-DOC-FORMAT.md (``repo``, ``default_url``, ``default_port`` and the
ordered section headings). Those apply to ``docs/products/<id>/product.md``,
which is a different and stricter shape than the flat knowledge-base
documents this module governs. See ADR 0011.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

import frontmatter
import yaml

# Kebab-case, because product_id is an identifier, not a label: it goes into
# ChromaDB metadata, into the FE product picker, and into eval case fixtures.
# The corpus already contains "klob mobile" and "learning hub mobile" — ids
# with spaces, created by a free-text field with no validation behind it. They
# still resolve, but they cannot be typed reliably or referenced from a test.
PRODUCT_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Mirrors the `status` values PRODUCT-DOC-FORMAT.md defines. `status` is
# promoted to chunk metadata (see indexing._chunk_metadata's allowlist), so a
# typo here silently opts a document out of any status-based filtering.
VALID_STATUSES = frozenset({"active", "maintained", "deprecated"})

REQUIRED_FIELDS = ("product_id", "product_name", "status")

# At least one markdown heading. The indexer splits on h1/h2/h3 before it
# splits on length (see indexing.chunk_file), and the heading path becomes the
# `heading_path` metadata that survives into retrieval. A document with no
# headings is one undifferentiated blob: retrievable, but with nothing to say
# which part of it matched. That matters more here than in a typical RAG
# corpus because the embedding model is English and the documents are
# Indonesian, so similarity scores are weak and structure carries the load.
HEADING_PATTERN = re.compile(r"^#{1,3} \S", re.MULTILINE)


def validate_document(text: str) -> list[str]:
    """Problems with one document's source, most structural first.

    Returns an empty list when the document is fine. Never raises for bad
    input — a malformed document is a result to report, not an exception to
    handle at every call site.
    """
    try:
        post = frontmatter.loads(text)
    except yaml.YAMLError as exc:
        # The failure that motivated all of this: a product_name containing a
        # colon produced YAML that broke the whole index build.
        first_line = str(exc).strip().splitlines()[0]
        return [f"frontmatter is not valid YAML: {first_line}"]
    except Exception as exc:  # noqa: BLE001 — see the "never raises" contract above
        # Deliberately blind. This function's whole job is to turn a bad
        # document into a reportable result, and it sits on the request path:
        # an unexpected parser error here would otherwise be a 500 on a
        # document the user could have fixed, or an aborted `just validate-docs`
        # run that never reaches the remaining files.
        return [f"could not parse document: {type(exc).__name__}: {exc}"]

    problems: list[str] = []
    meta = post.metadata

    for field in REQUIRED_FIELDS:
        value = meta.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            problems.append(f"missing required frontmatter field: {field}")

    product_id = meta.get("product_id")
    if isinstance(product_id, str) and product_id.strip():
        if not PRODUCT_ID_PATTERN.match(product_id.strip()):
            problems.append(
                f"product_id '{product_id}' is not kebab-case "
                "(lowercase letters, digits and single hyphens)"
            )

    status = meta.get("status")
    if isinstance(status, str) and status.strip() and status.strip() not in VALID_STATUSES:
        problems.append(f"status '{status}' is not one of: {', '.join(sorted(VALID_STATUSES))}")

    # Optional today, always written by the API since the ownership change.
    # Checked when present so a hand-edited document cannot introduce a format
    # the staleness report will not understand.
    last_reviewed = meta.get("last_reviewed")
    if last_reviewed is not None:
        if not _is_iso_date(last_reviewed):
            problems.append(f"last_reviewed '{last_reviewed}' is not an ISO date (YYYY-MM-DD)")

    owner = meta.get("owner")
    if owner is not None and (not isinstance(owner, str) or not owner.strip()):
        problems.append("owner is present but empty")

    body = post.content.strip()
    if not body:
        problems.append("document body is empty")
    elif not HEADING_PATTERN.search(body):
        problems.append(
            "document body has no markdown heading (#, ## or ###) — "
            "retrieval cannot tell its sections apart without one"
        )

    return problems


def validate_file(path: Path) -> list[str]:
    """:func:`validate_document` for a file on disk."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"could not read file: {exc}"]
    return validate_document(text)


def _is_iso_date(value: object) -> bool:
    """True for a `datetime.date` or a 'YYYY-MM-DD' string.

    PyYAML parses an unquoted ``2026-08-19`` into a ``date`` object, so both
    representations reach us depending on how the document was written.
    """
    if isinstance(value, datetime.date):
        return True
    if not isinstance(value, str):
        return False
    try:
        datetime.date.fromisoformat(value.strip())
    except ValueError:
        return False
    return True


def main() -> int:
    """``just validate-docs`` — check every knowledge-base document.

    Returns a process exit code so CI fails on a corpus that would break, or
    that would retrieve badly, rather than discovering it from a bad answer.
    """
    from .settings import REPO_ROOT

    kb_dir = REPO_ROOT / "docs" / "knowledge-base"
    if not kb_dir.exists():
        print(f"[validate-docs] no knowledge-base directory at {kb_dir} — nothing to check")
        return 0

    # Sorted so CI output is stable and diffable between runs.
    paths = sorted(kb_dir.glob("*.md"))
    if not paths:
        print("[validate-docs] no documents found")
        return 0

    total_problems = 0
    for path in paths:
        problems = validate_file(path)
        if not problems:
            print(f"[validate-docs] OK   {path.name}")
            continue
        total_problems += len(problems)
        print(f"[validate-docs] FAIL {path.name}")
        for problem in problems:
            print(f"[validate-docs]        - {problem}")

    print(f"[validate-docs] {len(paths)} document(s) checked, {total_problems} problem(s) found")
    return 1 if total_problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
