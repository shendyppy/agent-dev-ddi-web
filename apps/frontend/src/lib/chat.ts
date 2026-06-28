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

// ─── Error copy mapper ────────────────────────────────────────────────
// Converts raw exception / SSE error strings into human-readable copy so the
// component's catch and SSE branches never surface a status code or stack
// trace to the user. Only the most actionable categories get specific copy;
// everything else falls back to the generic "try again" message.

export function mapErrorToFriendly(raw: string, copy: Copy): string {
  const s = raw.toLowerCase();
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
