"""Tests for the knowledge-base write path, the review inbox, and the indexer.

These lock the failures that were all silent-until-catastrophic:

1. Frontmatter built by string interpolation. A ``product_name`` containing a
   colon — "Klob: Mobile App" — produced invalid YAML, and because the file was
   written *before* indexing ran, the bad document survived and broke every
   later ``just index`` for the whole team.
2. Unconditional overwrite. Two documents whose titles sanitize to the same
   slug destroyed each other with no version, no diff, no undo.
3. ``build_index`` aborting on the first unparseable file, so one bad document
   cost you the entire index rather than just itself.
4. Submissions landing straight in the answering corpus with no review, and a
   full ~60s corpus rebuild on every save.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter
import pytest
import yaml
from fastapi import HTTPException

from . import indexing as indexing_module
from . import server as server_module
from .server import (
    KnowledgeBaseRequest,
    create_knowledge_base,
    list_knowledge_base_inbox,
    publish_knowledge_base,
)

TEST_AUTHOR = "penulis@example.com"
TEST_MAINTAINER = "maintainer@example.com"


@pytest.fixture
def kb_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the endpoints at a temp repo root; stub indexing and git.

    The endpoints import REPO_ROOT from .settings at call time, so patching the
    settings module is what takes effect. Indexing and git are stubbed because
    these tests are about what lands on disk and in what order; their own
    behaviour is covered separately.

    Returns the PUBLISHED directory. Submissions land in ``_inbox/`` beneath it.
    """
    from . import settings as settings_module

    monkeypatch.setattr(settings_module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server_module, "index_single_file", lambda path: 7)
    monkeypatch.setattr(server_module, "commit_paths", lambda *a, **k: "abc1234")
    return tmp_path / "docs" / "knowledge-base"


def _request(**overrides: Any) -> KnowledgeBaseRequest:
    base = {
        "filename": "fitur-login",
        "product_id": "klob",
        "product_name": "Klob.id",
        "content": "# Fitur Login\n\nPenjelasan singkat.",
    }
    return KnowledgeBaseRequest(**{**base, **overrides})


def _submit(**overrides: Any) -> dict[str, str]:
    """Call the endpoint the way FastAPI would, with the dependency resolved."""
    return create_knowledge_base(_request(**overrides), author_email=TEST_AUTHOR)


class TestFrontmatterSafety:
    def test_colon_in_product_name_still_parses(self, kb_root: Path) -> None:
        """The exact input that used to brick the index. A colon is ordinary
        punctuation in a product name, not an edge case."""
        _submit(product_name="Klob: Mobile App")

        post = frontmatter.load(kb_root / "_inbox" / "fitur-login.md")
        assert post.metadata["product_name"] == "Klob: Mobile App"
        assert post.metadata["product_id"] == "klob"
        assert post.metadata["status"] == "active"

    def test_content_opening_with_a_fence_does_not_swallow_the_body(self, kb_root: Path) -> None:
        """Content starting with `---` used to be ambiguous with the closing
        frontmatter fence."""
        _submit(content="---\n\n# Judul\n\nIsi.")

        post = frontmatter.load(kb_root / "_inbox" / "fitur-login.md")
        assert post.metadata["product_id"] == "klob"
        assert "Isi." in post.content

    def test_indonesian_text_is_not_escaped_on_disk(self, kb_root: Path) -> None:
        _submit(product_name="Pusat Pembelajaran — Ponsel")

        raw = (kb_root / "_inbox" / "fitur-login.md").read_text(encoding="utf-8")
        assert "Pusat Pembelajaran — Ponsel" in raw
        assert "\\u" not in raw


class TestOwnershipIsRecorded:
    def test_owner_and_last_reviewed_are_filled_in_server_side(self, kb_root: Path) -> None:
        """Asking the user for these guarantees they rot. Deriving them costs
        the user nothing and makes staleness reportable."""
        import datetime

        result = _submit()

        post = frontmatter.load(kb_root / "_inbox" / "fitur-login.md")
        assert post.metadata["owner"] == TEST_AUTHOR
        assert post.metadata["last_reviewed"] == datetime.date.today().isoformat()
        assert result["owner"] == TEST_AUTHOR

    def test_the_commit_sha_is_reported_back(self, kb_root: Path) -> None:
        assert _submit()["commit"] == "abc1234"


class TestReviewInbox:
    def test_a_submission_is_not_published_and_not_indexed(
        self, kb_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The quarantine property. A submission must not be answerable until
        somebody has looked at it."""
        indexed: list[Path] = []
        monkeypatch.setattr(server_module, "index_single_file", lambda p: indexed.append(p) or 0)

        result = _submit()

        assert result["status"] == "pending_review"
        assert (kb_root / "_inbox" / "fitur-login.md").exists()
        assert not (kb_root / "fitur-login.md").exists()
        assert indexed == [], "a document awaiting review must not be indexed"

    def test_the_inbox_is_invisible_to_the_indexer_discoverer(self, kb_root: Path) -> None:
        """Why the inbox is a SUBdirectory: discovery globs *.md
        non-recursively, so quarantine costs no indexer changes at all."""
        _submit()
        from . import settings as settings_module

        monkeypatch_free_dir = settings_module.REPO_ROOT / "docs" / "knowledge-base"
        discovered = list(monkeypatch_free_dir.glob("*.md"))

        assert discovered == []

    def test_inbox_listing_reports_what_is_waiting(self, kb_root: Path) -> None:
        _submit(filename="fitur-login")
        _submit(filename="fitur-logout")

        listing = list_knowledge_base_inbox(_maintainer=TEST_MAINTAINER)

        names = {d["file"] for d in listing["documents"]}
        assert names == {"fitur-login.md", "fitur-logout.md"}
        assert all(d["owner"] == TEST_AUTHOR for d in listing["documents"])


class TestPublishing:
    def test_publishing_moves_the_file_and_indexes_it(self, kb_root: Path) -> None:
        _submit()

        result = publish_knowledge_base("fitur-login.md", maintainer_email=TEST_MAINTAINER)

        assert result["status"] == "published"
        assert (kb_root / "fitur-login.md").exists()
        assert not (kb_root / "_inbox" / "fitur-login.md").exists()
        assert result["chunks"] == "7"

    def test_publishing_something_absent_is_a_404(self, kb_root: Path) -> None:
        with pytest.raises(HTTPException) as excinfo:
            publish_knowledge_base("tidak-ada.md", maintainer_email=TEST_MAINTAINER)

        assert excinfo.value.status_code == 404

    def test_publish_path_parameter_cannot_traverse(self, kb_root: Path) -> None:
        """The filename reaches a filesystem join, so it is re-slugified rather
        than trusted."""
        with pytest.raises(HTTPException) as excinfo:
            publish_knowledge_base("../../../etc/passwd", maintainer_email=TEST_MAINTAINER)

        assert excinfo.value.status_code == 404

    def test_a_document_hand_edited_into_invalidity_is_refused(self, kb_root: Path) -> None:
        """Documents can rot between submission and review."""
        _submit()
        (kb_root / "_inbox" / "fitur-login.md").write_text(
            "---\nproduct_name: Klob: Mobile\n---\n\nisi\n", encoding="utf-8"
        )

        with pytest.raises(HTTPException) as excinfo:
            publish_knowledge_base("fitur-login.md", maintainer_email=TEST_MAINTAINER)

        assert excinfo.value.status_code == 422


class TestOverwriteProtection:
    def test_collision_is_refused_with_409(self, kb_root: Path) -> None:
        _submit(content="# Judul\n\nversi pertama")

        with pytest.raises(HTTPException) as excinfo:
            _submit(content="# Judul\n\nversi kedua")

        assert excinfo.value.status_code == 409
        assert "fitur-login.md" in str(excinfo.value.detail)
        # The original survives untouched — that is the whole point.
        assert "versi pertama" in (kb_root / "_inbox" / "fitur-login.md").read_text(
            encoding="utf-8"
        )

    def test_a_published_name_is_also_taken(self, kb_root: Path) -> None:
        """Collision is checked against both directories: a name already
        published is just as taken as one waiting for review."""
        _submit()
        publish_knowledge_base("fitur-login.md", maintainer_email=TEST_MAINTAINER)

        with pytest.raises(HTTPException) as excinfo:
            _submit()

        assert excinfo.value.status_code == 409
        assert "published" in str(excinfo.value.detail)

    def test_different_titles_that_sanitize_alike_collide(self, kb_root: Path) -> None:
        """ "FAQ" and "faq!!!" both become faq.md. Silent data loss used to
        follow; now the second one is refused."""
        _submit(filename="FAQ", content="# FAQ\n\nasli")

        with pytest.raises(HTTPException) as excinfo:
            _submit(filename="faq!!!", content="# FAQ\n\npengganti")

        assert excinfo.value.status_code == 409

    def test_overwrite_flag_is_honoured(self, kb_root: Path) -> None:
        _submit(content="# Judul\n\nversi pertama")
        _submit(content="# Judul\n\nversi kedua", overwrite=True)

        assert "versi kedua" in (kb_root / "_inbox" / "fitur-login.md").read_text(encoding="utf-8")

    def test_filename_cannot_escape_the_knowledge_base_directory(self, kb_root: Path) -> None:
        """Path separators become literal hyphens, so traversal is not
        expressible. Locked so a future 'nicer slugs' rewrite cannot regress it."""
        _submit(filename="../../etc/passwd")

        written = list((kb_root / "_inbox").glob("*.md"))
        assert len(written) == 1
        assert written[0].parent == kb_root / "_inbox"


class TestValidationGate:
    """The endpoint refuses a bad document instead of writing it.

    "Nothing invalid reaches disk" is the property that makes the indexer's
    per-file guard a safety net rather than the only defence.
    """

    def test_document_without_a_heading_is_refused_and_not_written(self, kb_root: Path) -> None:
        with pytest.raises(HTTPException) as excinfo:
            _submit(content="paragraf tanpa heading")

        assert excinfo.value.status_code == 422
        assert "heading" in str(excinfo.value.detail)
        assert not (kb_root / "_inbox" / "fitur-login.md").exists()

    def test_non_kebab_product_id_is_refused(self, kb_root: Path) -> None:
        """Stops the next 'klob mobile' at the door rather than in the corpus."""
        with pytest.raises(HTTPException) as excinfo:
            _submit(product_id="klob mobile")

        assert excinfo.value.status_code == 422
        assert "kebab-case" in str(excinfo.value.detail)
        assert not (kb_root / "_inbox" / "fitur-login.md").exists()


class TestIncrementalIndexing:
    """`index_single_file` replaces a ~60s full rebuild with a scoped write.

    The properties that matter: it touches only the file it was given, it
    *replaces* rather than appends, and its cost does not depend on how big
    the rest of the corpus is.
    """

    @pytest.fixture
    def fake_index(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
        recorded: dict[str, Any] = {"deleted": [], "upserted": None}

        class FakeCollection:
            def delete(self, **kwargs: Any) -> None:
                recorded["deleted"].append(kwargs)

            def upsert(self, **kwargs: Any) -> None:
                recorded["upserted"] = kwargs

        monkeypatch.setattr(indexing_module, "_get_client", lambda: object())
        monkeypatch.setattr(indexing_module, "_get_collection", lambda _: FakeCollection())
        monkeypatch.setattr(indexing_module, "_embed_texts", lambda texts: [[0.0] for _ in texts])
        monkeypatch.setattr(indexing_module, "_is_tep_web", lambda _: False)
        monkeypatch.setattr(indexing_module, "_relative_source", lambda p: Path(p).name)
        monkeypatch.setattr(indexing_module, "_display_source", lambda p: Path(p).name)
        return recorded

    def test_only_the_given_file_is_replaced(
        self, tmp_path: Path, fake_index: dict[str, Any]
    ) -> None:
        doc = tmp_path / "fitur-login.md"
        doc.write_text(
            "---\nproduct_id: klob\nproduct_name: Klob.id\n---\n\n# Judul\n\nIsi.\n",
            encoding="utf-8",
        )

        count = indexing_module.index_single_file(doc)

        assert count > 0
        # Scoped delete, not a full-collection scan.
        assert fake_index["deleted"] == [{"where": {"source": "fitur-login.md"}}]
        assert all(cid.startswith("fitur-login.md::") for cid in fake_index["upserted"]["ids"])

    def test_delete_happens_even_when_the_file_yields_no_chunks(
        self, tmp_path: Path, fake_index: dict[str, Any]
    ) -> None:
        """A document emptied of content must stop being retrievable. Skipping
        the delete would leave the old version answering questions forever."""
        doc = tmp_path / "kosong.md"
        doc.write_text("---\nproduct_id: klob\nproduct_name: Klob.id\n---\n\n", encoding="utf-8")

        count = indexing_module.index_single_file(doc)

        assert count == 0
        assert fake_index["deleted"] == [{"where": {"source": "kosong.md"}}]
        assert fake_index["upserted"] is None

    def test_embedder_is_reused_across_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Constructing TextEmbedding spins up an ONNX session. Doing that per
        save is what made the old code slow before it even started work."""
        constructed = []

        class FakeEmbedding:
            def __init__(self, model_name: str) -> None:
                constructed.append(model_name)

            def embed(self, texts: list[str]) -> list[Any]:
                return []

        monkeypatch.setattr(indexing_module, "TextEmbedding", FakeEmbedding)
        monkeypatch.setattr(indexing_module, "_embedder", None)

        indexing_module._get_embedder()
        indexing_module._get_embedder()

        assert len(constructed) == 1


class TestIndexerToleratesBadFiles:
    def test_chunk_file_raises_on_unparseable_frontmatter(self, tmp_path: Path) -> None:
        """The underlying failure the guard exists to contain."""
        bad = tmp_path / "bad.md"
        bad.write_text("---\nproduct_name: Klob: Mobile App\n---\n\nisi\n", encoding="utf-8")

        with pytest.raises(yaml.YAMLError):
            indexing_module.chunk_file(bad)

    def test_build_index_skips_the_bad_file_and_indexes_the_rest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """One malformed document must cost that document only."""
        good = tmp_path / "good.md"
        good.write_text(
            "---\nproduct_id: klob\nproduct_name: Klob.id\n---\n\n# Judul\n\nIsi.\n",
            encoding="utf-8",
        )
        bad = tmp_path / "bad.md"
        bad.write_text("---\nproduct_name: Klob: Mobile App\n---\n\nisi\n", encoding="utf-8")

        upserted: dict[str, Any] = {}

        class FakeCollection:
            def get(self, **_: Any) -> dict[str, list[str]]:
                return {"ids": []}

            def upsert(self, **kwargs: Any) -> None:
                upserted.update(kwargs)

            def delete(self, **_: Any) -> None:
                pass

            def count(self) -> int:
                return len(upserted.get("ids", []))

        monkeypatch.setattr(indexing_module, "SOURCE_DISCOVERERS", [lambda: [good, bad]])
        # Patch the accessor, not PersistentClient: the accessor memoises into
        # a module global, which would otherwise leak a fake between tests.
        monkeypatch.setattr(indexing_module, "_get_client", lambda: object())
        monkeypatch.setattr(indexing_module, "_get_collection", lambda _: FakeCollection())
        monkeypatch.setattr(indexing_module, "_embed_texts", lambda texts: [[0.0] for _ in texts])
        monkeypatch.setattr(indexing_module, "_relative_source", lambda p: Path(p).name)
        monkeypatch.setattr(indexing_module, "_display_source", lambda p: Path(p).name)
        monkeypatch.setattr(indexing_module, "_is_tep_web", lambda _: False)

        indexing_module.build_index()

        # It completed, and the good file made it in.
        assert upserted["ids"], "the good document should still have been indexed"
        assert all(cid.startswith("good.md::") for cid in upserted["ids"])

        out = capsys.readouterr().out
        assert "SKIPPED bad.md" in out
        assert "1 file(s) skipped" in out

    def test_pruning_spares_chunks_of_a_file_that_failed_to_parse(self) -> None:
        """A file that breaks today should keep serving yesterday's answers
        rather than silently vanishing from retrieval."""
        deleted: list[list[str]] = []

        class FakeCollection:
            def get(self, **_: Any) -> dict[str, list[str]]:
                return {"ids": ["bad.md::0", "bad.md::1", "gone.md::0"]}

            def delete(self, ids: list[str]) -> None:
                deleted.append(ids)

        removed = indexing_module._prune_stale_chunks(
            FakeCollection(),  # type: ignore[arg-type]
            current_ids=set(),
            protected_prefixes={"bad.md"},
        )

        assert removed == 1
        assert deleted == [["gone.md::0"]]
