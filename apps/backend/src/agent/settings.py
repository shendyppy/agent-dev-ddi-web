"""Centralized settings loaded from the repo-root .env file.

All env access in the codebase goes through this module. Never read os.environ
directly elsewhere — it makes the contract implicit and untestable.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    # All providers go through LiteLLM (see ADR 0003) — set LITELLM_MODEL
    # to switch and provide the matching key below. Unused keys are fine.
    # Full provider list + format examples: .env.example.
    litellm_model: str = "gemini-2.5-flash"
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    openai_api_key: str | None = None

    # Vector store
    chroma_persist_dir: Path = REPO_ROOT / ".data" / "chroma"

    # Observability
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None

    # Ports
    frontend_port: int = 4321
    backend_port: int = 8000

    # MCP
    mcp_transport: str = "stdio"


settings = Settings()
