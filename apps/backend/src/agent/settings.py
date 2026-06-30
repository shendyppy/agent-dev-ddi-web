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

    # Retry policy (applied in agent.llm around every litellm call). The
    # cheaper/free Gemini tiers regularly throw transient 503 ("high demand")
    # and 429s; retrying with exponential backoff turns a momentary hiccup
    # into a short wait instead of a dead chat stream. `litellm_max_attempts`
    # is the TOTAL number of attempts including the first, so 4 = 1 try + up
    # to 3 retries.
    litellm_max_attempts: int = 4
    litellm_retry_max_wait: float = 20.0  # cap on a single backoff sleep (s)

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

    # Screenshot capture (capture_screenshot MCP skill + the /screenshots mount
    # in server.py). Playwright PNGs land in `screenshot_dir`; FastAPI serves
    # them at /screenshots. `screenshot_base_url` is the absolute URL the agent
    # embeds in its markdown image — it MUST be reachable from the browser, and
    # since the FE runs on a different port than the BE, it has to be absolute
    # (a relative "/screenshots/x.png" would resolve against the FE origin).
    # Keep the host:port in sync with BACKEND_PORT.
    screenshot_dir: Path = REPO_ROOT / ".data" / "screenshots"
    screenshot_base_url: str = "http://localhost:8000"

    # External source corpus: the tep-web repo (the Acelents website) whose
    # source we index as the "acelents" product (see indexing.discover_tep_web_source).
    # Host-specific absolute path — override TEP_WEB_ROOT for other contributors
    # or CI. Outside REPO_ROOT on purpose: it is a separate project we ingest.
    tep_web_root: Path = Path("C:/Project/DDI/Acelents/tep-web")


settings = Settings()
