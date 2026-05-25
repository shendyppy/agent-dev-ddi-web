"""Prompt loader.

Reads versioned prompt files from `prompts/` (repo-root) and renders them
with simple {{placeholder}} substitution.

Per AGENTS.md: never inline multi-line prompts as Python strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import frontmatter

from .settings import REPO_ROOT

PROMPTS_DIR = REPO_ROOT / "prompts"
_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


@dataclass
class Prompt:
    name: str
    version: int
    model: str | None
    body: str
    metadata: dict

    def render(self, **kwargs: object) -> str:
        missing: list[str] = []

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in kwargs:
                missing.append(key)
                return match.group(0)
            return str(kwargs[key])

        rendered = _PLACEHOLDER.sub(replace, self.body)
        if missing:
            raise ValueError(
                f"Prompt {self.name!r} missing inputs: {sorted(set(missing))}"
            )
        return rendered


def load(name: str) -> Prompt:
    """Load a prompt by name. Searches system/ first, then tools/."""
    for sub in ("system", "tools"):
        path = PROMPTS_DIR / sub / f"{name}.md"
        if path.exists():
            post = frontmatter.load(path)
            return Prompt(
                name=post.get("name", name),
                version=int(post.get("version", 1)),
                model=post.get("model"),
                body=post.content,
                metadata=dict(post.metadata),
            )
    raise FileNotFoundError(f"Prompt {name!r} not found under {PROMPTS_DIR}")
