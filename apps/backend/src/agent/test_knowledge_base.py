"""Tests for the knowledge-base write path and the indexer's tolerance of bad files.

These lock three failures that were all silent-until-catastrophic:

1. Frontmatter built by string interpolation. A ``product_name`` containing a
   colon — "Klob: Mobile App" — produced invalid YAML, and because the file was
   written *before* indexing ran, the bad document survived and broke every
   later ``just index`` for the whole team.
2. Unconditional overwrite. Two documents whose titles sanitize to the same
   slug destroyed each other with no version, no diff, no undo.
3. ``build_index`` aborting on the first unparseable file, so one bad document
   cost you the entire index rather than just itself.
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
from .server import KnowledgeBaseRequest, create_knowledge_base


@pytest.fixture
def kb_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the endpoint at a temp repo root and stub out the reindex.

    ``create_knowledge_base`` imports REPO_ROOT from .settings at call time, so
    patching the settings module is what takes effect. The subprocess is
    stubbed because these tests are about what lands on disk, not about
    indexing — and a real ``just index`` takes ~60s.
    """
    from . import settings as settings_module

    monkeypatch.setattr(settings_module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server_module.subprocess, "run", lambda *a, **k: None)
    return tmp_path / "docs" / "knowledge-base"


def _request(**overrides: Any) -> KnowledgeBaseRequest:
    base = {
        "filename": "fitur-login",
        "product_id": "klob",
        "product_name": "Klob.id",
        "content": "# Fitur Login\n\nPenjelasan singkat.",
    }
    return KnowledgeBaseRequest(**{**base, **overrides})


class TestFrontmatterSafety:
    def test_colon_in_product_name_still_parses(self, kb_root: Path) -> None:
        """The exact input that used to brick the index. A colon is ordinary
        punctuation in a product name, not an edge case."""
        create_knowledge_base(_request(product_name="Klob: Mobile App"))

        post = frontmatter.load(kb_root / "fitur-login.md")
        assert post.metadata["product_name"] == "Klob: Mobile App"
        assert post.metadata["product_id"] == "klob"
        assert post.metadata["status"] == "active"

    def test_content_opening_with_a_fence_does_not_swallow_the_body(self, kb_root: Path) -> None:
        """Content starting with `---` used to be ambiguous with the closing
        frontmatter fence."""
        create_knowledge_base(_request(content="---\n\n# Judul\n\nIsi."))

        post = frontmatter.load(kb_root / "fitur-login.md")
        assert post.metadata["product_id"] == "klob"
        assert "Isi." in post.content

    def test_indonesian_text_is_not_escaped_on_disk(self, kb_root: Path) -> None:
        create_knowledge_base(_request(product_name="Pusat Pembelajaran — Ponsel"))

        raw = (kb_root / "fitur-login.md").read_text(encoding="utf-8")
        assert "Pusat Pembelajaran — Ponsel" in raw
        assert "\\u" not in raw


class TestOverwriteProtection:
    def test_collision_is_refused_with_409(self, kb_root: Path) -> None:
        create_knowledge_base(_request(content="versi pertama"))

        with pytest.raises(HTTPException) as excinfo:
            create_knowledge_base(_request(content="versi kedua"))

        assert excinfo.value.status_code == 409
        assert "fitur-login.md" in str(excinfo.value.detail)
        # The original survives untouched — that is the whole point.
        assert "versi pertama" in (kb_root / "fitur-login.md").read_text(encoding="utf-8")

    def test_different_titles_that_sanitize_alike_collide(self, kb_root: Path) -> None:
        """ "FAQ" and "faq!!!" both become faq.md. Silent data loss used to
        follow; now the second one is refused."""
        create_knowledge_base(_request(filename="FAQ", content="asli"))

        with pytest.raises(HTTPException) as excinfo:
            create_knowledge_base(_request(filename="faq!!!", content="pengganti"))

        assert excinfo.value.status_code == 409

    def test_overwrite_flag_is_honoured(self, kb_root: Path) -> None:
        create_knowledge_base(_request(content="versi pertama"))
        create_knowledge_base(_request(content="versi kedua", overwrite=True))

        assert "versi kedua" in (kb_root / "fitur-login.md").read_text(encoding="utf-8")

    def test_filename_cannot_escape_the_knowledge_base_directory(self, kb_root: Path) -> None:
        """Path separators become literal hyphens, so traversal is not
        expressible. Locked so a future 'nicer slugs' rewrite cannot regress it."""
        create_knowledge_base(_request(filename="../../etc/passwd"))

        written = list(kb_root.glob("*.md"))
        assert len(written) == 1
        assert written[0].parent == kb_root


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
        monkeypatch.setattr(indexing_module, "PersistentClient", lambda **_: object())
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
