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
    # NOTE: Google retires Gemini model ids for *new* users without warning —
    # `gemini-2.5-flash` and `gemini-2.5-flash-lite` both began returning 404
    # ("no longer available to new users") in Jul 2026, even though they still
    # appear in the ListModels response. Verify a candidate with a real
    # generateContent call before pinning it here; ListModels is not proof.
    litellm_model: str = "gemini/gemini-3.6-flash"
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

    # Offline UI mode. When true, agent.llm short-circuits every completion to
    # a fixture in agent/fixtures/ and NO provider request is made.
    #
    # Why this exists: the Gemini key is free tier, capped at 20 requests per
    # DAY per model. Frontend work burns that in a handful of reloads and then
    # the chat is dead until the quota resets — which makes it impossible to
    # check how an answer *renders*. The fixture is also strictly better for
    # that job than a real model: it is deterministic and it deliberately
    # exercises every markdown branch the transcript can hit.
    #
    # Dev-only. It bypasses the model entirely, so never enable it anywhere a
    # real answer is expected — including eval runs, which would all trivially
    # "pass" against the fixture.
    llm_fake_mode: bool = False
    llm_fake_latency_seconds: float = 0.6  # so the typing indicator is visible

    # When true (the default), fake mode first emits a real
    # `search_documentation` tool call, so the graph queries the LOCAL ChromaDB
    # index and the answer is built from chunks that actually exist in the
    # corpus — real text, real `Sources:` paths. Retrieval is free, so this
    # costs nothing and additionally exercises the tool-chip and
    # message-grouping UI that a single-shot fixture never reaches.
    #
    # Set false to get the static markdown fixture instead, which is the better
    # choice when the thing under test is markdown rendering itself (it covers
    # every element on purpose). Fake mode also falls back to the fixture
    # automatically when the index is missing or empty.
    llm_fake_use_retrieval: bool = True

    # Agent loop guard (applied in agent.graph). The graph loops
    # llm → tools → llm for as long as the model keeps asking for tools, and
    # nothing in that loop is self-limiting: a model that keeps re-searching
    # burns one full-history LLM call plus a subprocess spawn per round, and
    # history grows with every tool result. `agent_max_tool_rounds` caps the
    # rounds; on hitting it the graph does one final LLM call with NO tools
    # offered, so the user gets an answer from the evidence already gathered
    # instead of a raw error. 6 is roughly double what a well-behaved answer
    # needs (1-3 rounds) — high enough not to truncate legitimate multi-step
    # research, low enough to stop a runaway early.
    agent_max_tool_rounds: int = 6

    # Pre-call input budget handed to token_killer. Tool results in this app
    # are large JSON blobs of retrieved chunks, so a long conversation can
    # push the request past the provider's context window; pruning drops the
    # oldest turns before that happens. Sized well under the 1M-token windows
    # of current Gemini/Claude models — the goal is cost control, not just
    # avoiding hard failures.
    agent_max_input_tokens: int = 60_000

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
