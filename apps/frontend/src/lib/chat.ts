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
  { signal, maxAttempts = 12 }: { signal?: AbortSignal; maxAttempts?: number } = {},
): Promise<T> {
  let lastError: unknown;

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const res = await fetch(`${API_BASE}${path}`, { signal });
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
  if (s.includes('429') || s.includes('rate') || s.includes('quota') || s.includes('resource_exhausted')) {
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
  const html = DOMPurify.sanitize(marked.parse(content) as string, {
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
