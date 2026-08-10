/**
 * Chat runtime — wire types + the non-UI helpers the chat island depends on.
 *
 * Kept separate from the components so the SSE parser, markdown sanitiser, and
 * error mapper can be unit-tested and reasoned about without any Preact in the
 * way. The component layer (hooks/use-chat + components/chat/*) imports from here.
 */
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import type { Copy } from './copy';

// ─── Wire types ──────────────────────────────────────────────────────
// Mirrors the backend message shape. Tool-call shape follows OpenAI's
// {function: {name, arguments}}; the backend's _to_openai_dict bridge
// (graph.py) is the contract enforcer.

export type ToolCall = {
  id: string;
  type?: string;
  function: { name: string; arguments: string };
};

export type Message = {
  role: 'user' | 'assistant' | 'tool';
  content?: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  name?: string;
  id?: string;
  isError?: boolean;
  // Evidence behind this answer, from the `retrieval` SSE event. Only ever set
  // on an assistant message that has content — see useChat's send().
  retrieval?: Retrieval;
};

// ─── Retrieval evidence ───────────────────────────────────────────────
// Mirrors the `retrieval` SSE frame documented in the backend's server.py.
// Produced by agent/relevance.py, which is the single source of truth for what
// counts as a relevant passage — nothing here is recomputed on the client.
//
// Both `score` and `overlap` are present on purpose. On this corpus the score
// alone is misleading: an English embedding model over Indonesian docs scores
// "resep rendang padang" (0.514) ABOVE "gimana cara menjalankan proyek ini di
// lokal" (0.501). Keyword overlap is what separates them, and showing the two
// side by side is what makes a rejected high-scoring passage make sense.

/** Why a passage did or did not make it into the answer. */
export type Verdict =
  /** Used as evidence. */
  | 'strong'
  /** Cleared every gate but lost the three-passage cap. */
  | 'weak'
  /** Failed the score floor or the keyword-overlap gate. */
  | 'rejected';

export type RankedChunk = {
  source: string;
  heading: string;
  /** 1 - chroma_distance. Higher is better; can exceed 1 or go negative. */
  score: number;
  /** Question words found in the passage; a heading hit counts double. */
  overlap: number;
  verdict: Verdict;
  excerpt: string;
};

export type Confidence = 'high' | 'medium' | 'low' | 'none';

export type Retrieval = {
  question: string;
  product_id: string | null;
  confidence: Confidence;
  chunks: RankedChunk[];
};

// One product the agent can answer about. Comes from GET /api/products,
// which derives it from the indexed docs — see the list_products MCP skill.
export type Product = {
  id: string;
  name: string;
  status?: string;
  doc_count?: number;
};

export const API_BASE = import.meta.env.PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

// ─── Model selection + BYOK ───────────────────────────────────────────
// Mirrors GET /api/models. See ADR 0010.
//
// The key lives in localStorage and is sent per request in a header — never in
// the request body, because `saveHistory` persists body-shaped data to Supabase
// and a credential must not be able to reach that table by accident.
//
// Known accepted risk: localStorage is readable by any XSS on the page. The main
// XSS surface here is LLM-authored markdown, already sanitised by DOMPurify.

export type ModelOption = {
  id: string;
  label: string;
  /** Context window and per-million pricing, straight from LiteLLM's registry. */
  note: string;
  /** LiteLLM provider name — used to group the list. */
  provider: string;
  /** Pinned to the top of the picker as a suggestion, not a restriction. */
  recommended: boolean;
  /** Which env var credentials this entry — shown so an unavailable option can
   *  tell the user what to go and get, instead of only refusing. */
  env_key: string;
  /** Whether the entry can be selected at all. */
  available: boolean;
  /** Where the credential comes from. `server` is guaranteed to authenticate;
   *  `your-key` means it will use the pasted key, which may belong to a
   *  different provider — we cannot tell, and guessing from the key's prefix
   *  would be a bet on a format the providers can change. */
  source: 'server' | 'your-key' | 'none';
};

export type ModelCatalogue = { models: ModelOption[]; default: string };

const MODEL_KEY_STORAGE = 'docagent.modelApiKey';
const MODEL_ID_STORAGE = 'docagent.modelId';

export function loadStoredApiKey(): string {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem(MODEL_KEY_STORAGE) ?? '';
}

export function storeApiKey(key: string): void {
  if (typeof window === 'undefined') return;
  if (key.trim()) window.localStorage.setItem(MODEL_KEY_STORAGE, key.trim());
  else window.localStorage.removeItem(MODEL_KEY_STORAGE);
}

export function loadStoredModelId(): string {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem(MODEL_ID_STORAGE) ?? '';
}

export function storeModelId(id: string): void {
  if (typeof window === 'undefined') return;
  if (id) window.localStorage.setItem(MODEL_ID_STORAGE, id);
  else window.localStorage.removeItem(MODEL_ID_STORAGE);
}

/** Headers carrying the model choice and the caller's key.
 *
 *  Built in one place so no call site can forget the "header, never body" rule.
 *  Omits each header entirely when empty — an empty `X-Model-Api-Key` would be
 *  read by the backend as a supplied-but-blank key rather than as absent. */
export function modelHeaders(
  modelId: string,
  apiKey: string,
  offline = false,
): Record<string, string> {
  const headers: Record<string, string> = {};
  if (modelId) headers['X-Model-Id'] = modelId;
  if (apiKey.trim()) headers['X-Model-Api-Key'] = apiKey.trim();
  // Sent only when on. The backend matches the literal "true", so an absent
  // header and an explicit "false" mean the same thing.
  if (offline) headers['X-Offline-Mode'] = 'true';
  return headers;
}

const OFFLINE_STORAGE = 'docagent.offlineMode';

export function loadStoredOffline(): boolean {
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem(OFFLINE_STORAGE) === 'true';
}

export function storeOffline(on: boolean): void {
  if (typeof window === 'undefined') return;
  if (on) window.localStorage.setItem(OFFLINE_STORAGE, 'true');
  else window.localStorage.removeItem(OFFLINE_STORAGE);
}

// ─── Bootstrap fetch with retry ───────────────────────────────────────
//
// `just dev` starts the frontend and the backend concurrently, and the
// frontend always wins: Astro is serving in ~2s while uvicorn is still
// importing the agent graph and loading the embedding model. Every bootstrap
// GET therefore lands on a closed port on first paint.
//
// Fetching once and swallowing the failure (which is what this used to do)
// turns that transient race into a permanent broken state: the model chip
// stays blank forever, and — worse — the product list resolves to `[]`, so the
// scope gate renders with no product cards and the user cannot get past it
// without reloading. Nothing recovers on its own, because nothing tries again.
//
// So: retry with exponential backoff until the backend answers.

const RETRY_BASE_MS = 300;
const RETRY_CAP_MS = 5_000;

/** A response the server actually produced. Distinct from a network failure. */
export class HttpError extends Error {
  constructor(readonly status: number) {
    super(`HTTP ${status}`);
    this.name = 'HttpError';
  }
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });
}

/**
 * GET JSON, retrying while the backend looks like it is still coming up.
 *
 * Retries a network error (port not open yet) or a 5xx (process up, not ready).
 * Does NOT retry a 4xx: that is the server giving a considered answer about
 * this request, and repeating it just repeats the same mistake.
 *
 * Backoff is capped at 5s so a backend that takes a while to boot is still
 * picked up promptly, without hammering the port while it is closed.
 */
export async function fetchJsonWithRetry<T>(
  path: string,
  {
    signal,
    maxAttempts = 12,
    headers,
  }: { signal?: AbortSignal; maxAttempts?: number; headers?: Record<string, string> } = {},
): Promise<T> {
  let lastError: unknown;

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const res = await fetch(`${API_BASE}${path}`, { signal, headers });
      if (res.ok) return (await res.json()) as T;
      if (res.status < 500) throw new HttpError(res.status); // caller's problem, not a race
      lastError = new HttpError(res.status);
    } catch (err) {
      // An abort is the component unmounting — propagate, never retry it.
      if (err instanceof DOMException && err.name === 'AbortError') throw err;
      if (err instanceof HttpError && err.status < 500) throw err;
      lastError = err;
    }

    if (attempt < maxAttempts - 1) {
      await delay(Math.min(RETRY_BASE_MS * 2 ** attempt, RETRY_CAP_MS), signal);
    }
  }

  throw lastError ?? new Error('unreachable');
}

// ─── Error copy mapper ────────────────────────────────────────────────
// Converts raw exception / SSE error strings into human-readable copy so the
// component's catch and SSE branches never surface a status code or stack
// trace to the user. Only the most actionable categories get specific copy;
// everything else falls back to the generic "try again" message.

export function mapErrorToFriendly(raw: string, copy: Copy): string {
  const s = raw.toLowerCase();
  // Loop guard first: the backend caps tool rounds and normally recovers by
  // forcing a final answer, so reaching here means the recursion backstop in
  // server.py tripped. It needs its own copy — "try again" is the one piece of
  // advice that definitely will not help, since the same question loops again.
  if (s.includes('recursion') || s.includes('graphrecursion')) {
    return copy.errorLoopGuard;
  }
  // A per-DAY quota must be checked BEFORE the generic 429 branch, which it
  // would otherwise match. The distinction is not cosmetic: errorRateLimit
  // tells the user to wait a moment and retry, and for a daily cap that is the
  // one thing guaranteed not to work. The provider payload carries the period
  // in its quotaId (e.g. "GenerateRequestsPerDayPerProjectPerModel-FreeTier"),
  // which reaches us inside the flattened exception string.
  if (s.includes('perday') || s.includes('per day') || s.includes('requests per day')) {
    return copy.errorQuotaExhausted;
  }
  if (
    s.includes('429') ||
    s.includes('rate') ||
    s.includes('quota') ||
    s.includes('resource_exhausted')
  ) {
    return copy.errorRateLimit;
  }
  if (s.includes('503') || s.includes('unavailable') || s.includes('overload')) {
    return copy.errorServiceUnavailable;
  }
  return copy.errorGeneric;
}

// ─── SSE parsing ─────────────────────────────────────────────────────
// Yields one {event, data} per server-sent event frame. Frames are separated
// by one blank line; we accept LF *or* CRLF endings because sse-starlette 3.x
// emits CRLF (`\r\n\r\n`) and splitting only on `\n\n` would silently drop
// every frame (the bug that surfaced as a phantom "connection dropped").

export async function* parseSSE(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<{ event: string; data: string }> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const FRAME_SEP = /\r?\n\r?\n/;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let match = FRAME_SEP.exec(buffer);
    while (match !== null) {
      const frame = buffer.slice(0, match.index);
      buffer = buffer.slice(match.index + match[0].length);

      let eventName = 'message';
      const dataLines: string[] = [];
      for (const line of frame.split(/\r?\n/)) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
      }
      yield { event: eventName, data: dataLines.join('\n') };

      match = FRAME_SEP.exec(buffer);
    }
  }
}

// ─── Sanitized markdown — memoised per message ───────────────────────
// marked.parse + DOMPurify.sanitize on every render gets expensive as the
// message list grows, so we cache by content string in a module-level Map.

const MD_CACHE = new Map<string, string>();

// Force target="_blank" rel="noopener noreferrer" on every link the LLM emits
// so a malicious URL can't tab-nap the parent. Registered once at module load.
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if ('target' in node) {
    (node as HTMLAnchorElement).setAttribute('target', '_blank');
    (node as HTMLAnchorElement).setAttribute('rel', 'noopener noreferrer');
  }
});

export function renderMarkdown(content: string): string {
  const cached = MD_CACHE.get(content);
  if (cached !== undefined) return cached;
  // Normalize Windows line endings BEFORE parsing. marked v18 copes with CRLF
  // for most blocks but NOT for GFM tables — every row falls out as its own
  // `<p>| … |</p>` paragraph, which is exactly the "raw pipe" mess offline
  // answers showed when quoting docs indexed on Windows. Headings survive
  // CRLF, tables do not, so this line is what keeps quoted tables rendering.
  const normalized = content.replace(/\r\n?/g, '\n');
  const html = DOMPurify.sanitize(marked.parse(normalized) as string, {
    ADD_ATTR: ['target', 'rel'],
  });
  MD_CACHE.set(content, html);
  return html;
}

// ─── Citation extraction ──────────────────────────────────────────────
// The main-agent prompt instructs the LLM to end grounded answers with a
// "Sources:" list of file paths or URLs it retrieved from tools. We parse
// that block out of the raw markdown so we can render it as a dedicated
// citation component instead of inline markdown text.
//
// Returns the answer body with the Sources block removed, plus the list
// of source strings. An empty array means "no citations present" — the
// component should render nothing.

const SOURCES_RE = /\n{0,2}\*{0,2}[Ss]ources?:?\*{0,2}\s*\n((?:[ \t]*[-*\d.]+\s*.+\n?)*)/;

export function extractCitations(content: string): { body: string; citations: string[] } {
  const match = SOURCES_RE.exec(content);
  if (!match) return { body: content, citations: [] };

  const citations = match[1]
    .split('\n')
    .map((line) => line.replace(/^[ \t]*[-*\d.]+\.?\s*/, '').trim())
    .filter(Boolean);

  const body = content.slice(0, match.index).trimEnd();
  return { body, citations };
}
