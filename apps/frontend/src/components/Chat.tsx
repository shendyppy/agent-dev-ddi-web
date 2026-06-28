/**
 * Chat island — the Preact component hydrated on every page.
 *
 * Loaded from `index.astro` with `client:load`. Talks to the FastAPI
 * orchestrator at `POST /api/chat` and consumes the Server-Sent Events
 * response in real time, appending each new message as it arrives.
 *
 * SSE contract — see `apps/backend/src/agent/server.py` for the source of
 * truth. Events we handle here:
 *
 *   event: message → JSON of one new message ({role, content, tool_calls?, …})
 *   event: error   → human-readable error string; we surface it as a
 *                    distinct error bubble with a Retry affordance.
 *   event: done    → terminator, carries the session_id so we can include
 *                    it on the next request (drives Langfuse trace
 *                    correlation across turns).
 *
 * Why no EventSource?
 *   `EventSource` only does GET. We need POST so the conversation
 *   history can be in the request body. Hence the fetch + ReadableStream
 *   + manual SSE parser below.
 */
import { useState, useRef, useEffect, useMemo, useCallback } from 'preact/hooks';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import './Chat.css';

// ─── Wire types ──────────────────────────────────────────────────────
// Mirrors the backend message shape. Tool-call shape follows OpenAI's
// {function: {name, arguments}}. The backend's _to_openai_dict bridge
// (graph.py) is the contract enforcer.

type ToolCall = {
  id: string;
  type?: string;
  function: { name: string; arguments: string };
};

type Message = {
  role: 'user' | 'assistant' | 'tool';
  content?: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  name?: string;
  id?: string;
  isError?: boolean;
};

// One product the agent can answer about. Comes from GET /api/products,
// which derives it from the indexed docs — see list_products MCP skill.
type Product = {
  id: string;
  name: string;
  status?: string;
  doc_count?: number;
};

const API_BASE = import.meta.env.PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
// Model label comes from the backend (GET /api/meta) — see useEffect in Chat().

// ─── Bilingual copy ──────────────────────────────────────────────────
// One flat object per language. The active language is held in state
// and persisted to localStorage. Every user-facing string in this
// component reads from here — never inline a literal string in JSX.

type Language = 'id' | 'en';

const COPY: Record<Language, {
  appTitle: string;
  langLabel: string;
  langToggleAria: string;
  welcomeHeading: (accent: string) => { lead: string; accent: string; trail: string };
  welcomeSubtitle: string;
  suggestedPrompts: string[];
  inputPlaceholder: string;
  inputLabel: string;
  sendLabel: string;
  sendAria: string;
  chatLogLabel: string;
  typingThinking: string;
  typingSearching: string;
  toolCalling: string;
  toolResult: (chars: number) => string;
  errorPrefix: string;
  errorHint: string;
  errorStreamDropped: string;
  errorRetry: string;
  productScopeLabel: string;
  productScopeAll: string;
  productScopeAria: string;
}> = {
  id: {
    appTitle: 'Documentation Agent',
    langLabel: 'Bahasa',
    langToggleAria: 'Ganti bahasa antarmuka',
    welcomeHeading: () => ({ lead: 'Ada yang bisa ', accent: 'dibantu', trail: '?' }),
    welcomeSubtitle:
      'Saya bisa bantu cari cara menjalankan produk, melihat fiturnya, navigasi UI, atau ambil screenshot — bisa pakai Bahasa Indonesia atau English.',
    suggestedPrompts: [
      'Cara menjalankan proyek di lokal?',
      'Fitur apa saja yang tersedia?',
      'Di mana cari dokumentasi tentang autentikasi?',
    ],
    inputPlaceholder: "Coba: 'Cara jalanin X?' atau 'Di mana fitur export-nya?'",
    inputLabel: 'Tulis pertanyaan',
    sendLabel: 'Kirim',
    sendAria: 'Kirim pesan (Enter)',
    chatLogLabel: 'Riwayat percakapan',
    typingThinking: 'Sedang berpikir…',
    typingSearching: 'Mencari di dokumentasi…',
    toolCalling: 'Mencari di dokumentasi…',
    toolResult: () => 'Konten ditemukan',
    errorPrefix: 'Ada yang error nih — coba kirim ulang pertanyaannya.',
    errorHint: 'Kalau terus muncul, ping #doc-agent di Slack.',
    errorStreamDropped: 'Koneksi terputus sebelum jawaban selesai. Coba lagi?',
    errorRetry: 'Coba lagi',
    productScopeLabel: 'Fokus:',
    productScopeAll: 'Semua produk',
    productScopeAria: 'Pilih produk yang ingin difokuskan',
  },
  en: {
    appTitle: 'Documentation Agent',
    langLabel: 'Language',
    langToggleAria: 'Change interface language',
    welcomeHeading: () => ({ lead: 'What can I ', accent: 'help', trail: ' with?' }),
    welcomeSubtitle:
      'I can look up how to run a product, list features, navigate the UI, or capture screenshots — ask in English or Bahasa.',
    suggestedPrompts: [
      'How do I run the project locally?',
      'What features are available?',
      'Where can I find docs about authentication?',
    ],
    inputPlaceholder: "Try: 'How do I run X?' or 'Where is the export feature?'",
    inputLabel: 'Type a question',
    sendLabel: 'Send',
    sendAria: 'Send message (Enter)',
    chatLogLabel: 'Conversation log',
    typingThinking: 'Thinking…',
    typingSearching: 'Searching the documentation…',
    toolCalling: 'Searching the documentation…',
    toolResult: () => 'Content found',
    errorPrefix: 'Something went wrong — please try again.',
    errorHint: 'If this keeps happening, contact #doc-agent on Slack.',
    errorStreamDropped: 'Connection dropped before the answer finished. Retry?',
    errorRetry: 'Retry',
    productScopeLabel: 'Focus:',
    productScopeAll: 'All products',
    productScopeAria: 'Pick a product to focus on',
  },
};

function loadInitialLang(): Language {
  if (typeof window === 'undefined') return 'id';
  const stored = window.localStorage.getItem('docagent.lang');
  return stored === 'en' ? 'en' : 'id';
}

// ─── SSE parsing ─────────────────────────────────────────────────────
// Pulled out as a generator so the component code below stays a single
// readable flow. Yields one {event, data} per server-sent event frame.

async function* parseSSE(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<{ event: string; data: string }> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Frames are separated by one blank line. Accept LF *or* CRLF endings:
    // the SSE spec allows both, native EventSource normalises both, and our
    // backend (sse-starlette 3.x) emits CRLF (`\r\n\r\n`). Splitting only on
    // `\n\n` silently drops every frame against a CRLF stream — see the bug
    // where the FE never received `done` and showed "connection dropped".
    const FRAME_SEP = /\r?\n\r?\n/;
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
// marked.parse + DOMPurify.sanitize on every render is expensive when
// the message list grows. We cache by content string in a module-level
// Map; cache survives re-mount but is bounded by chat session length.

const MD_CACHE = new Map<string, string>();
function renderMarkdown(content: string): string {
  let html = MD_CACHE.get(content);
  if (html !== undefined) return html;
  html = DOMPurify.sanitize(marked.parse(content) as string, {
    ADD_ATTR: ['target', 'rel'],
  });
  MD_CACHE.set(content, html);
  return html;
}

// Force `target="_blank" rel="noopener noreferrer"` on every link the
// LLM emits so a malicious URL can't tab-nap the parent. DOMPurify hooks
// run during sanitize() so this is the right place to enforce it.
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if ('target' in node) {
    (node as HTMLAnchorElement).setAttribute('target', '_blank');
    (node as HTMLAnchorElement).setAttribute('rel', 'noopener noreferrer');
  }
});

// ─── Small UI primitives ─────────────────────────────────────────────

function AssistantAvatar() {
  return (
    <div class="avatar" aria-hidden="true">
      <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
      </svg>
    </div>
  );
}

function LanguageToggle({
  lang,
  onChange,
  copy,
}: {
  lang: Language;
  onChange: (next: Language) => void;
  copy: (typeof COPY)['id'];
}) {
  return (
    <div class="lang-toggle" role="group" aria-label={copy.langToggleAria}>
      <button
        type="button"
        aria-pressed={lang === 'id'}
        onClick={() => onChange('id')}
      >
        ID
      </button>
      <button
        type="button"
        aria-pressed={lang === 'en'}
        onClick={() => onChange('en')}
      >
        EN
      </button>
    </div>
  );
}

// ─── Component ───────────────────────────────────────────────────────

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [lang, setLang] = useState<Language>(loadInitialLang);
  const [modelLabel, setModelLabel] = useState<string>('');
  const [products, setProducts] = useState<Product[]>([]);
  const [activeProductId, setActiveProductId] = useState<string | null>(null);
  const endOfMessagesRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const copy = COPY[lang];

  // Fetch the active model label once on mount. Backend is the single
  // source of truth — swap LITELLM_MODEL in .env and this chip reflects
  // it on next load, with no FE env var to keep in sync.
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/meta`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data?.model) setModelLabel(data.model);
      })
      .catch(() => {
        // Backend down/unreachable — leave chip empty rather than throw.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Fetch the product catalogue once on mount to populate the scope picker.
  // Backend derives this from the indexed docs (GET /api/products), so adding
  // a doc + reindexing makes a new product appear here with no FE change.
  // Empty list (index not built, backend down) → picker simply isn't shown.
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/products`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && Array.isArray(data?.products)) setProducts(data.products);
      })
      .catch(() => {
        // Backend unreachable — leave the picker hidden rather than throw.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Persist language choice across reloads.
  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('docagent.lang', lang);
    }
  }, [lang]);

  // Auto-scroll to the latest message. During streaming we use 'auto'
  // (instant) so rapid appends don't queue overlapping smooth-scrolls
  // and thrash; once the turn ends we use 'smooth' for the final settle.
  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({
      behavior: busy ? 'auto' : 'smooth',
    });
  }, [messages, busy]);

  const handleInput = (e: Event) => {
    const target = e.target as HTMLTextAreaElement;
    setInput(target.value);
    target.style.height = 'auto';
    target.style.height = `${Math.min(target.scrollHeight, 200)}px`;
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  // Mint a sequence-based key for each appended message so Preact can
  // diff cheaply (and correctly if we ever reorder/delete).
  const nextId = useRef(0);
  const withId = useCallback((m: Message): Message => ({ ...m, id: m.id ?? `m${nextId.current++}` }), []);

  async function send(overrideInput?: string) {
    const text = (overrideInput ?? input).trim();
    if (!text || busy) return;

    const userMessage: Message = withId({ role: 'user', content: text });
    const historyForRequest = [...messages, userMessage];
    setMessages(historyForRequest);
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setBusy(true);

    let receivedDone = false;

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: historyForRequest
            .filter((m) => m.role === 'user' || (m.role === 'assistant' && m.content))
            .map((m) => ({ role: m.role, content: m.content ?? '' })),
          session_id: sessionId,
          product_id: activeProductId,
        }),
      });

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`);
      }

      for await (const { event, data } of parseSSE(res.body)) {
        if (event === 'message') {
          try {
            const msg: Message = JSON.parse(data);
            setMessages((prev) => [...prev, withId(msg)]);
          } catch {
            setMessages((prev) => [
              ...prev,
              withId({
                role: 'assistant',
                content: `(malformed event payload: ${data})`,
                isError: true,
              }),
            ]);
          }
        } else if (event === 'error') {
          setMessages((prev) => [
            ...prev,
            withId({ role: 'assistant', content: data, isError: true }),
          ]);
        } else if (event === 'done') {
          receivedDone = true;
          if (data) setSessionId(data);
        }
      }

      // Stream closed without a `done` event → connection dropped. Surface
      // a recoverable error instead of leaving the user with a frozen UI.
      if (!receivedDone) {
        setMessages((prev) => [
          ...prev,
          withId({ role: 'assistant', content: copy.errorStreamDropped, isError: true }),
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        withId({ role: 'assistant', content: String(err), isError: true }),
      ]);
    } finally {
      setBusy(false);
      // Return focus so the next message is one keystroke away.
      textareaRef.current?.focus();
    }
  }

  // Typing-indicator label: if the last appended message is an assistant
  // bubble with tool_calls only, the model is mid-retrieval; otherwise
  // it's reasoning over text. Surfacing this turns generic dots into a
  // status signal without any backend change.
  const typingLabel = useMemo(() => {
    const last = messages[messages.length - 1];
    if (last?.role === 'assistant' && last.tool_calls?.length && !last.content) {
      return copy.typingSearching;
    }
    if (last?.role === 'tool') return copy.typingThinking;
    return copy.typingThinking;
  }, [messages, copy]);

  // ─── Rendering helpers ──────────────────────────────────────────────

  const renderAssistantMarkdown = (content: string) => (
    <div
      class="message-content markdown-body"
      dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
    />
  );

  const renderToolCallChip = () => (
    // We deliberately do NOT show the raw function name or arguments —
    // those are developer-only details. The user sees "the bot is
    // working" affordance only. Full tool detail is in Langfuse traces.
    <div class="message-content tool-meta">
      <span class="tool-chip">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.3-4.3" />
        </svg>
        {copy.toolCalling}
      </span>
    </div>
  );

  const renderToolResultChip = (msg: Message) => (
    <div class="message-content tool-meta tool-result">
      <span class="tool-chip">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 6L9 17l-5-5" />
        </svg>
        {copy.toolResult(msg.content?.length ?? 0)}
      </span>
    </div>
  );

  const renderErrorBubble = (content: string) => (
    <div class="error-bubble" role="alert">
      <p>{copy.errorPrefix}</p>
      <p class="error-hint">{content}</p>
      <p class="error-hint">{copy.errorHint}</p>
      <button type="button" onClick={() => send(messages.filter((m) => m.role === 'user').slice(-1)[0]?.content ?? '')}>
        {copy.errorRetry}
      </button>
    </div>
  );

  const headingParts = copy.welcomeHeading('');

  return (
    <div class="app-container">
      <header class="header">
        <div class="header-title">
          <span class="header-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </span>
          <h1>{copy.appTitle}</h1>
        </div>
        <div class="header-actions">
          <span class="model-chip" title={modelLabel ? `Model: ${modelLabel}` : 'Model: …'}>
            {modelLabel || '…'}
          </span>
          <LanguageToggle lang={lang} onChange={setLang} copy={copy} />
        </div>
      </header>

      <div class="chat-container">
        <div
          class="chat-content"
          role="log"
          aria-live="polite"
          aria-atomic="false"
          aria-label={copy.chatLogLabel}
        >
          {messages.length === 0 ? (
            <div class="welcome-message">
              <h2>
                {headingParts.lead}
                <span class="accent">{headingParts.accent}</span>
                {headingParts.trail}
              </h2>
              <p>{copy.welcomeSubtitle}</p>
              <div class="prompt-chip-row">
                {copy.suggestedPrompts.map((p) => (
                  <button
                    type="button"
                    class="prompt-chip"
                    key={p}
                    onClick={() => {
                      setInput(p);
                      textareaRef.current?.focus();
                    }}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => {
              if (m.role === 'user') {
                return (
                  <div key={m.id} class="message-wrapper user">
                    <div class="message user">
                      <div class="message-content">{m.content}</div>
                    </div>
                  </div>
                );
              }
              if (m.role === 'tool') {
                return (
                  <div key={m.id} class="message-wrapper assistant">
                    <div class="message assistant">
                      <AssistantAvatar />
                      {renderToolResultChip(m)}
                    </div>
                  </div>
                );
              }
              const hasContent = (m.content ?? '').trim().length > 0;
              const hasToolCalls = m.tool_calls && m.tool_calls.length > 0;
              if (!hasContent && !hasToolCalls) return null;
              return (
                <div key={m.id} class="message-wrapper assistant">
                  <div class="message assistant">
                    <AssistantAvatar />
                    {m.isError
                      ? renderErrorBubble(m.content ?? '')
                      : hasContent
                        ? renderAssistantMarkdown(m.content as string)
                        : renderToolCallChip()}
                  </div>
                </div>
              );
            })
          )}

          {busy && (
            <div class="message-wrapper assistant">
              <div class="message assistant">
                <AssistantAvatar />
                <div class="message-content">
                  <div class="typing-indicator">
                    <span class="typing-dots">
                      <span class="typing-dot" />
                      <span class="typing-dot" />
                      <span class="typing-dot" />
                    </span>
                    <span>{typingLabel}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={endOfMessagesRef} />
        </div>
      </div>

      <div class="input-container">
        {products.length > 0 && (
          <div class="scope-bar" role="group" aria-label={copy.productScopeAria}>
            <span class="scope-label">{copy.productScopeLabel}</span>
            <div class="scope-chips">
              <button
                type="button"
                class={`scope-chip${activeProductId === null ? ' is-active' : ''}`}
                aria-pressed={activeProductId === null}
                onClick={() => setActiveProductId(null)}
              >
                {copy.productScopeAll}
              </button>
              {products.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  class={`scope-chip${activeProductId === p.id ? ' is-active' : ''}`}
                  aria-pressed={activeProductId === p.id}
                  onClick={() => setActiveProductId(p.id)}
                  title={p.name}
                >
                  {p.name}
                </button>
              ))}
            </div>
          </div>
        )}
        <div class="input-box">
          <label class="visually-hidden" htmlFor="chat-input">
            {copy.inputLabel}
          </label>
          <textarea
            ref={textareaRef}
            id="chat-input"
            class="input-textarea"
            value={input}
            onInput={handleInput}
            onKeyDown={handleKeyDown}
            placeholder={copy.inputPlaceholder}
            aria-label={copy.inputLabel}
            disabled={busy}
            rows={1}
          />
          <button
            type="button"
            class="send-button"
            onClick={() => send()}
            disabled={busy || !input.trim()}
            title={copy.sendLabel}
            aria-label={copy.sendAria}
          >
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
