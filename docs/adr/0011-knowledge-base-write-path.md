# ADR 0011 — Knowledge-base write path: review inbox, git history, incremental indexing

- **Status**: Accepted
- **Date**: 2026-08-19
- **Amends**: ADR 0006 (per-product documentation format — this ADR states explicitly that the flat `docs/knowledge-base/` corpus is a first-class second shape, not a migration backlog)

## Context

PR #10 added a web form that writes documentation straight into the corpus the agent answers from. It worked, and it exposed that we had never decided how documents get in. Reviewing it surfaced five problems, all of which were live in `development`.

**1. Two documentation formats, no decision between them.** ADR 0006 specifies `docs/products/<id>/` with eight required frontmatter fields and ordered headings. Two folders use it: `_template/` and `acelents/`. Meanwhile all ten real documents live flat in `docs/knowledge-base/` with three frontmatter fields, and that is where the form wrote. The spec was already de-facto abandoned; the form made the abandonment permanent without anyone choosing it.

**2. One document could break indexing for everyone, permanently.** Frontmatter was built by f-string interpolation, so a `product_name` as ordinary as `Klob: Mobile App` produced invalid YAML — verified: `ScannerError`. `build_index()` had no per-file guard, so the whole run aborted. The file was written *before* indexing ran, so it survived the failure and broke every subsequent `just index` until a human found it by hand.

**3. No review, no history, no ownership.** Submissions became answerable immediately, which is how a knowledge base ends up with two documents confidently contradicting each other. Files were written outside git entirely: no diff, no blame, no revert, no record of who wrote what — and, on a container filesystem, no survival past the next deploy. `owner` and `last_reviewed` were never captured, so staleness was unmeasurable.

**4. No authentication.** The endpoint accepted an anonymous POST. The frontend rendered the button behind `user &&`, which is a rendering decision, not a security one.

**5. Every save rebuilt the entire index.** Measured: 58s for 639 chunks. Roughly 95% of that work was the external `tep-web` source corpus, which cannot change because somebody saved a markdown file. The cost grew with the corpus, heading for the reverse-proxy timeout — at which point the browser reports failure while the server keeps working.

Two constraints shaped the fixes. The embedding model is English while the corpus is Indonesian, so similarity scores are weak and document **structure** carries most of the retrieval signal. And this is a ~5-10 person internal team, so anything requiring a curated process before it works at all will simply go unused.

## Decision

| Choice | Reason |
|---|---|
| **`docs/knowledge-base/` is the corpus the form writes to**; `docs/products/` remains valid for hand-authored per-product folders | Matches where the documents actually are. ADR 0006's *reasoning* (structure drives retrieval) is upheld by the outline-prefilling form, not by forcing a folder shape nobody adopted |
| **Submissions land in `docs/knowledge-base/_inbox/`** and are not indexed until published | Review gate at zero cost: `discover_knowledge_base` globs `*.md` **non-recursively**, so the inbox is invisible to the indexer without the indexer knowing it exists |
| **Two roles: writer submits, maintainer publishes** | Two is what the workflow has. An empty writer allowlist means "any signed-in user" so the feature works before anyone curates a list |
| **Supabase `/auth/v1/user` verifies the bearer token** | No JWT secret to distribute or rotate, and a revoked session stops working immediately rather than at token expiry |
| **One shared validator** (`doc_validation.validate_document`), called pre-write (422) and by `just validate-docs` | One definition of "valid". A second copy would drift, silently |
| **`owner` and `last_reviewed` filled server-side** from the session and today's date | Fields the user is asked for are fields that rot. Zero extra inputs, and staleness becomes reportable |
| **Every change is a git commit**, authored by the submitter | Buys diff, blame, revert, audit trail and durability in one step. Non-fatal on failure — losing the audit trail must not lose the document |
| **`index_single_file()` replaces the full rebuild**, in-process, under a `threading.Lock` | 58s → ~2s, and flat as the corpus grows. `threading`, not `asyncio`: the endpoint is a sync `def`, so it runs in a threadpool worker |
| **Frontend rebuilt on shadcn/Tailwind**; `antd` and `ckeditor5` removed | They were a second design system in the main chat bundle for every visitor. CKEditor emits HTML, which `MarkdownHeaderTextSplitter` cannot see at all — every document authored in it would have collapsed into heading-less blobs |
| **`product_id` chosen from `GET /api/products`**, not typed | Free text is how the corpus got `klob mobile` and `learning hub mobile`. Both fixed to kebab-case as part of this change |

## Alternatives considered

| Option | Rejected because |
|---|---|
| One uniform flat template for every document | This is precisely what ADR 0006 rejected. `klob-doc-context.md` is the in-repo proof: ~20 topics in one file, and with a mismatched embedder every chunk scores in the same band, so retrieval cannot separate "cara login" from "cara melamar" |
| Keep the rich-text editor (CKEditor) | `editor.getData()` returns HTML; the chunker splits on `#`/`##`/`###` and cannot see `<h2>`. It was a latent corpus-destroying bug, not a deferred nice-to-have |
| Migrate everything into `docs/products/` first | A migration nobody had done in three months is not a prerequisite anybody will meet. Decide where documents live, then improve them in place |
| Full reindex in a background task with status polling | Fixes the blocked request, not the waste: still 58s of CPU re-embedding unrelated chunks per save, and it needs a job-status UI |
| A job queue (Celery/RQ) | Needs a long-running worker, which works against ADR 0005's scale-to-zero cost goal, for a problem incremental indexing removes outright |
| Verify JWTs locally with the project secret | Another secret to distribute and rotate, and revoked sessions would keep working until expiry |
| No review step, publish on submit | The state we were in. For a corpus with a single write path and no undo, one contradictory document is worse than one slow submission |

## Consequences

**Positive:**
- One malformed document costs that document, not the index. Its previously-indexed chunks are also spared from pruning, so it keeps serving its last good answers until fixed.
- Nothing invalid reaches disk: the validator runs before the write.
- A save takes ~2s instead of 58s, and stays flat as the corpus grows.
- Every document has a verified owner, a review date, and a git commit.
- `just validate-docs` exists, closing a TODO open since ADR 0006, and is CI-gateable.
- The frontend ships 163 fewer packages and one design system.

**Negative:**
- Publishing is a second, manual step. Deliberate, but it is friction, and if the inbox goes unwatched documents will sit there — the inbox listing endpoint exists so a maintainer UI can be built when that starts to bite.
- The index lock is process-local. A `just index` run started by hand during a save is still outside its reach; the failure is obvious and recoverable by reindexing.
- Auth requires Supabase to be configured. Unset means the write endpoints refuse — fail-closed, but it does mean local dev needs the same env as production.
- Two documentation shapes still coexist. This ADR makes that a decision rather than an accident, but the cost is that contributors must know which one they are writing.

## See also

- [`docs/PRODUCT-DOC-FORMAT.md`](../PRODUCT-DOC-FORMAT.md) — the per-product spec, still authoritative for `docs/products/`
- [ADR 0006 — Per-product documentation format](0006-product-doc-format.md)
- [ADR 0004 — RAG stack](0004-rag-stack.md) — the chunking strategy the structure rules exist to feed
- [ADR 0005 — Deployment strategy](0005-deployment-strategy.md) — why durability of the written files needed deciding
- [ADR 0009 — Enforced product scope](0009-enforced-product-scope-and-loop-guard.md) — why a typo'd `product_id` silently removes a document from retrieval
