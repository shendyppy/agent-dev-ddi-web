"""Tests for committing knowledge-base changes to git.

Documents written through the web form used to exist only as files on the
server's disk — no diff, no blame, no revert, no record of who wrote what.
These lock both halves of the fix: that a commit really happens and carries the
submitter as author, and that a git failure degrades instead of taking the save
down with it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from . import kb_git
from .kb_git import commit_paths


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A real, empty git repository with one commit already in it."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "seed@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Seed"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=tmp_path, check=True)
    return tmp_path


class TestCommitting:
    def test_a_new_document_is_committed_and_attributed(self, git_repo: Path) -> None:
        doc = git_repo / "docs" / "knowledge-base" / "fitur-login.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("# Fitur Login\n", encoding="utf-8")

        sha = commit_paths(
            git_repo, [doc], "docs(kb): submit fitur-login.md", "penulis@example.com"
        )

        assert sha, "expected a commit sha"
        log = subprocess.run(
            ["git", "-C", str(git_repo), "log", "-1", "--format=%an <%ae>%n%s"],
            capture_output=True,
            check=True,
        ).stdout.decode()
        # Author is the submitter, so `git log --author` answers "what has this
        # person documented?" directly.
        assert "penulis@example.com" in log
        assert "docs(kb): submit fitur-login.md" in log

    def test_the_file_is_actually_tracked_afterwards(self, git_repo: Path) -> None:
        doc = git_repo / "docs" / "kb.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# x\n", encoding="utf-8")

        commit_paths(git_repo, [doc], "docs(kb): add", "a@b.com")

        tracked = subprocess.run(
            ["git", "-C", str(git_repo), "ls-files", "docs/kb.md"],
            capture_output=True,
            check=True,
        ).stdout.decode()
        assert "docs/kb.md" in tracked

    def test_no_paths_means_no_commit(self, git_repo: Path) -> None:
        assert commit_paths(git_repo, [], "nothing", "a@b.com") is None


class TestFailuresAreNonFatal:
    def test_missing_git_binary_returns_none_instead_of_raising(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`git` absent is a realistic container state. The document is already
        saved and indexed by this point; losing the audit trail must not lose
        the document."""

        def explode(*_: object, **__: object) -> None:
            raise FileNotFoundError("git")

        monkeypatch.setattr(kb_git.subprocess, "run", explode)
        doc = tmp_path / "x.md"
        doc.write_text("# x\n", encoding="utf-8")

        assert commit_paths(tmp_path, [doc], "msg", "a@b.com") is None

    def test_not_a_repository_returns_none(self, tmp_path: Path) -> None:
        doc = tmp_path / "x.md"
        doc.write_text("# x\n", encoding="utf-8")

        assert commit_paths(tmp_path, [doc], "msg", "a@b.com") is None

    def test_committing_an_unchanged_file_returns_none(self, git_repo: Path) -> None:
        """git exits non-zero on an empty commit. That is a no-op, not a
        failure worth surfacing as an error."""
        doc = git_repo / "docs" / "kb.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# x\n", encoding="utf-8")
        commit_paths(git_repo, [doc], "first", "a@b.com")

        assert commit_paths(git_repo, [doc], "again", "a@b.com") is None
