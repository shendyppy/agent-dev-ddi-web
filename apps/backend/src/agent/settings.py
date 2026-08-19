"""Centralized settings loaded from the repo-root .env file.

All env access in the codebase goes through this module. Never read os.environ
directly elsewhere — it makes the contract implicit and untestable.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


def resolve_from_repo_root(value: Path) -> Path:
    """Anchor a possibly-relative path to the repo root instead of the cwd.

    ``.env`` ships relative paths (``CHROMA_PERSIST_DIR=./.data/chroma``), and
    a bare ``Path("./.data/chroma")`` resolves against whatever directory the
    process happens to be started in. That silently forked the vector store in
    two: ``just index`` runs ``cd apps/backend`` and wrote to
    ``apps/backend/.data/chroma``, while anything launched from the repo root
    read ``<root>/.data/chroma`` and found an empty index. It looked fine in
    normal dev only because ``just dev-be`` also cd's into ``apps/backend``.

    Absolute values are left alone, so pointing the store at a mounted volume
    still works.
    """
    return value if value.is_absolute() else (REPO_ROOT / value).resolve()


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

    # Generic provider credential — the last environment layer of
    # llm.resolve_api_key (ADR 0010). Use this when you run ONE model and do not
    # want to remember a vendor-specific variable name: set LITELLM_MODEL and
    # MODEL_API_KEY and you are done.
    #
    # It replaced three fields (`anthropic_api_key`, `gemini_api_key`,
    # `openai_api_key`) that were declared here and never read by anything.
    # Authentication had been working only because `import litellm` calls
    # `load_dotenv()` and loads the whole repo-root .env into os.environ — which
    # made this module's "all env access goes through here" docstring untrue.
    #
    # Per-provider variables (GEMINI_API_KEY, DEEPSEEK_API_KEY, …) are still
    # honoured and take precedence; they are read straight from os.environ
    # rather than declared here, because LiteLLM ships 141 providers and
    # enumerating them as fields is what produced the dead code above.
    model_api_key: str | None = None
    # Override the provider endpoint. Needed for self-hosted or
    # OpenAI-compatible gateways (vLLM, LM Studio, a corporate proxy), which a
    # key alone cannot describe. Left unset for hosted providers.
    model_api_base: str | None = None

    # Retry policy (applied in agent.llm around every litellm call). The
    # cheaper/free Gemini tiers regularly throw transient 503 ("high demand")
    # and 429s; retrying with exponential backoff turns a momentary hiccup
    # into a short wait instead of a dead chat stream. `litellm_max_attempts`
    # is the TOTAL number of attempts including the first, so 4 = 1 try + up
    # to 3 retries.
    litellm_max_attempts: int = 4
    litellm_retry_max_wait: float = 20.0  # cap on a single backoff sleep (s)

    # Offline mode OVERRIDE — force it on for the whole process. Normally you
    # do not touch this: agent.llm switches itself offline for a couple of
    # minutes whenever the provider answers with a capacity error (429/503/
    # timeout), so a busy or quota-exhausted model produces a grounded local
    # answer instead of an error bubble. See agent.llm's "Automatic offline
    # fallback" section for the windows.
    #
    # Setting it true is useful for one job: frontend work. The Gemini key is
    # free tier, capped at 20 requests per DAY per model, and forcing offline
    # mode means UI iteration never touches that budget at all. It also makes
    # the answer deterministic, which the real model is not.
    #
    # Dev-only. It bypasses the model entirely, so never enable it anywhere a
    # real answer is expected — including eval runs, which would all trivially
    # "pass" against the fixture.
    llm_fake_mode: bool = False
    # Pause before a forced-offline reply so the typing indicator is visible.
    # Ignored on automatic fallback — that path has already spent seconds
    # failing and retrying.
    llm_fake_latency_seconds: float = 0.6

    # When true (the default), an offline answer starts with a real
    # `search_documentation` tool call, so the graph queries the LOCAL ChromaDB
    # index and the answer quotes chunks that actually exist in the corpus —
    # real text, real `Sources:` paths. Retrieval is free, so this costs
    # nothing, and it is what makes an outage still useful to the user.
    #
    # Set false to get the static markdown fixture instead, which is the better
    # choice when the thing under test is markdown rendering itself (it covers
    # every element on purpose). Only sensible together with LLM_FAKE_MODE=true.
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

    # Comma-separated list of origins allowed to call /api/*. Leave empty in
    # local development and any loopback origin is accepted, which is what lets
    # contributors run the frontend on whatever port is free.
    #
    # SET THIS BEFORE DEPLOYING. `allow_credentials=True` plus a permissive
    # origin rule would let an origin we did not intend make credentialed
    # requests — and since ADR 0010 those requests can carry a user's provider
    # key in `X-Model-Api-Key`.
    cors_allowed_origins: str = ""

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        """Parsed :attr:`cors_allowed_origins`, empty when unset."""
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    # Supabase. The frontend signs users in; the backend verifies the resulting
    # access token before letting anyone write to the corpus. These read the
    # same PUBLIC_* names the frontend already uses — the anon key is shipped
    # to the browser, so it is not a secret and there is no second copy to keep
    # in sync. Unset means the write endpoints refuse rather than fall open.
    supabase_url: str = Field(default="", validation_alias="PUBLIC_SUPABASE_URL")
    supabase_anon_key: str = Field(default="", validation_alias="PUBLIC_SUPABASE_ANON_KEY")

    # BOOTSTRAP ONLY — who may publish knowledge-base documents before any role
    # has been granted. The real list lives in the `kb_roles` table in Supabase
    # (see supabase/migrations/), because a list of people is data, not config:
    # it changes when somebody joins or leaves, not when we deploy.
    #
    # This survives solely to break the chicken-and-egg — somebody has to be
    # able to grant the first role. Keep it to the one or two people who
    # administer the deployment. It is checked BEFORE the table, so it still
    # works against an empty database.
    #
    # Comma-separated; an entry may be a full email (`a@b.com`) or a domain
    # suffix (`@company.com`). There is no writer equivalent: submitting is open
    # to any signed-in user, because submissions are quarantined in the review
    # inbox and are not searchable until a maintainer publishes them.
    kb_maintainer_emails: str = ""

    @property
    def kb_maintainer_list(self) -> list[str]:
        """Parsed :attr:`kb_maintainer_emails`, empty when unset."""
        return [e.strip().lower() for e in self.kb_maintainer_emails.split(",") if e.strip()]

    # MCP
    mcp_transport: str = "stdio"

    # Screenshot capture (capture_screenshot MCP skill + the /screenshots mount
    # in server.py). Playwright PNGs land in `screenshot_dir`; FastAPI serves
    # them at /screenshots. `screenshot_base_url` is the absolute URL the agent
    # embeds in its markdown image — it MUST be reachable from the browser, and
    # since the FE runs on a different port than the BE, it has to be absolute
    # (a relative "/screenshots/x.png" would resolve against the FE origin).
    #
    # Left unset it FOLLOWS backend_port — see _follow_backend_port below. It
    # used to be a hardcoded ":8000" with a comment asking you to keep it in
    # sync by hand, which stopped being viable once `just dev` started picking
    # the port dynamically: every screenshot URL would point at whatever else
    # happened to own 8000. Set SCREENSHOT_BASE_URL explicitly to override
    # (deployments behind a proxy need to).
    screenshot_dir: Path = REPO_ROOT / ".data" / "screenshots"
    screenshot_base_url: str = "http://localhost:8000"

    # External source corpus: the tep-web repo (the Acelents website) whose
    # source we index as the "acelents" product (see indexing.discover_tep_web_source).
    # Host-specific absolute path — override TEP_WEB_ROOT for other contributors
    # or CI. Outside REPO_ROOT on purpose: it is a separate project we ingest.
    tep_web_root: Path = Path("C:/Project/DDI/Acelents/tep-web")

    @field_validator("chroma_persist_dir", "screenshot_dir", mode="after")
    @classmethod
    def _anchor_to_repo_root(cls, value: Path) -> Path:
        return resolve_from_repo_root(value)

    @model_validator(mode="after")
    def _follow_backend_port(self) -> Settings:
        """Point ``screenshot_base_url`` at ``backend_port`` unless it was set.

        ``model_fields_set`` is what makes this safe: it holds only the fields
        that actually came from the environment or the constructor, so an
        explicit SCREENSHOT_BASE_URL always wins and only the *default* moves.
        Without this, running the backend on any port other than 8000 produced
        screenshot URLs the browser could not fetch — and the agent embeds
        those URLs in its answers, so the failure surfaced as broken images in
        a chat reply rather than as anything resembling a port problem.
        """
        if "screenshot_base_url" not in self.model_fields_set:
            self.screenshot_base_url = f"http://localhost:{self.backend_port}"
        return self


settings = Settings()
