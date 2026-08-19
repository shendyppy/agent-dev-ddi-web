"""Tests for the shared knowledge-base document validator.

The validator is the gate that lets everything else be safe: the API refuses a
bad document with a 422 instead of writing it, and `just validate-docs` catches
a document that rotted after it was written. Both call validate_document, so
these tests cover both.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .doc_validation import validate_document, validate_file


def _doc(frontmatter_lines: str = "", body: str = "# Judul\n\nIsi dokumen.") -> str:
    default = "product_id: klob\nproduct_name: Klob.id\nstatus: active\n"
    return f"---\n{frontmatter_lines or default}---\n\n{body}\n"


class TestAcceptsGoodDocuments:
    def test_a_well_formed_document_has_no_problems(self) -> None:
        assert validate_document(_doc()) == []

    def test_optional_owner_and_last_reviewed_are_accepted(self) -> None:
        text = _doc(
            "product_id: klob\n"
            "product_name: Klob.id\n"
            "status: active\n"
            "owner: shendyppy@gmail.com\n"
            "last_reviewed: 2026-08-19\n"
        )
        assert validate_document(text) == []

    def test_a_colon_in_a_quoted_product_name_is_fine(self) -> None:
        """What the API now writes via yaml.safe_dump."""
        text = _doc("product_id: klob\nproduct_name: 'Klob: Mobile App'\nstatus: active\n")
        assert validate_document(text) == []


class TestCatchesTheFailuresThatBrokeTheIndex:
    def test_unquoted_colon_is_reported_not_raised(self) -> None:
        """The original outage: this used to propagate out of build_index and
        abort the entire run. The validator must return it, never raise it."""
        text = _doc("product_id: klob\nproduct_name: Klob: Mobile App\nstatus: active\n")

        problems = validate_document(text)

        assert len(problems) == 1
        assert "not valid YAML" in problems[0]

    def test_missing_required_fields_are_each_named(self) -> None:
        problems = validate_document(_doc("status: active\n"))

        assert any("product_id" in p for p in problems)
        assert any("product_name" in p for p in problems)

    def test_empty_required_field_counts_as_missing(self) -> None:
        text = _doc("product_id: klob\nproduct_name: '  '\nstatus: active\n")
        assert any("product_name" in p for p in validate_document(text))


class TestProductIdShape:
    def test_spaces_are_rejected(self) -> None:
        """Both real offenders in the corpus — 'klob mobile' and 'learning hub
        mobile' — came from a free-text field with nothing checking it."""
        text = _doc("product_id: klob mobile\nproduct_name: Klob Mobile\nstatus: active\n")

        problems = validate_document(text)

        assert any("kebab-case" in p for p in problems)

    @pytest.mark.parametrize("product_id", ["klob", "klob-mobile", "dash-admin-saas", "tep2"])
    def test_valid_ids_pass(self, product_id: str) -> None:
        text = _doc(f"product_id: {product_id}\nproduct_name: X\nstatus: active\n")
        assert validate_document(text) == []

    @pytest.mark.parametrize("product_id", ["Klob", "klob_mobile", "-klob", "klob--mobile"])
    def test_invalid_ids_fail(self, product_id: str) -> None:
        text = _doc(f"product_id: {product_id}\nproduct_name: X\nstatus: active\n")
        assert any("kebab-case" in p for p in validate_document(text))


class TestOtherFields:
    def test_unknown_status_is_rejected(self) -> None:
        text = _doc("product_id: klob\nproduct_name: X\nstatus: aktif\n")
        assert any("status" in p for p in validate_document(text))

    def test_non_iso_last_reviewed_is_rejected(self) -> None:
        text = _doc(
            "product_id: klob\nproduct_name: X\nstatus: active\nlast_reviewed: 19-08-2026\n"
        )
        assert any("last_reviewed" in p for p in validate_document(text))


class TestBodyStructure:
    def test_empty_body_is_rejected(self) -> None:
        assert any("body is empty" in p for p in validate_document(_doc(body="   ")))

    def test_body_without_a_heading_is_rejected(self) -> None:
        """A heading-less document chunks into context-free blobs. That matters
        more here than usual: the embedder is English, the corpus is
        Indonesian, so structure is what retrieval has left to work with."""
        text = _doc(body="Ini paragraf panjang tanpa heading sama sekali.")

        assert any("no markdown heading" in p for p in validate_document(text))


class TestValidateFile:
    def test_reads_and_validates_a_real_file(self, tmp_path: Path) -> None:
        path = tmp_path / "ok.md"
        path.write_text(_doc(), encoding="utf-8")

        assert validate_file(path) == []

    def test_missing_file_is_reported_not_raised(self, tmp_path: Path) -> None:
        problems = validate_file(tmp_path / "nope.md")

        assert len(problems) == 1
        assert "could not read file" in problems[0]


class TestTheRealCorpusStaysValid:
    def test_every_shipped_knowledge_base_document_passes(self) -> None:
        """A regression guard on the corpus itself, not just the validator.
        `just validate-docs` runs this same check in CI."""
        from .settings import REPO_ROOT

        kb_dir = REPO_ROOT / "docs" / "knowledge-base"
        failures = {
            path.name: problems
            for path in sorted(kb_dir.glob("*.md"))
            if (problems := validate_file(path))
        }

        assert not failures, f"invalid documents in the corpus: {failures}"
