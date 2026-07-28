/**
 * useChat — all chat state + side effects in one hook.
 *
 * Pulling this out of the component keeps Chat.tsx a thin layout/template:
 * it just wires the returned values into the header / message list / composer.
 * Owns: message list, input, busy flag, session id, language, model label,
 * product catalogue + active scope, and the send() round-trip (fetch + SSE).
 */
import { useState, useRef, useEffect, useMemo, useCallback } from 'preact/hooks';
import { COPY, loadInitialLang, type Language } from '@/lib/copy';
import {
  API_BASE,
  fetchJsonWithRetry,
  parseSSE,
  mapErrorToFriendly,
  type Message,
  type Product,
} from '@/lib/chat';

/** Bootstrap connectivity, surfaced so the gate can explain itself instead of
 *  rendering as an empty, dead screen while the backend is still booting. */
export type BackendStatus = 'connecting' | 'ready' | 'unreachable';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [lang, setLang] = useState<Language>(loadInitialLang);
  const [modelLabel, setModelLabel] = useState('');
  const [products, setProducts] = useState<Product[]>([]);
  // True while the product catalogue is still being fetched — including across
  // retries, so the gate keeps showing its skeleton instead of briefly
  // resolving to "no products" every time an attempt fails.
  const [productsLoading, setProductsLoading] = useState(true);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('connecting');
  // Bumping this re-runs both bootstrap effects — the manual "try again" the
  // gate offers once the automatic retries are exhausted.
  const [bootstrapNonce, setBootstrapNonce] = useState(0);
  const retryBootstrap = useCallback(() => {
    setProductsLoading(true);
    setBackendStatus('connecting');
    setBootstrapNonce((n) => n + 1);
  }, []);
  const [activeProductId, setActiveProductId] = useState<string | null>(null);
  // Whether the user has passed the scope gate. This has to be its own flag,
  // NOT `activeProductId !== null`: null now means two different things —
  // "hasn't chosen yet" and "deliberately chose all products" — and the whole
  // point of the gate is that those two stop being the same state.
  //
  // Deliberately not persisted. A reload clears the transcript, which makes it
  // a new conversation, and a new conversation should pick its own scope.
  const [scopeChosen, setScopeChosen] = useState(false);

  // Single entry point for both the gate and the header picker, so passing the
  // gate can never be forgotten at one of the call sites.
  const chooseScope = useCallback((id: string | null) => {
    setActiveProductId(id);
    setScopeChosen(true);
  }, []);

  const endOfMessagesRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const copy = COPY[lang];

  // Active model label (GET /api/meta). Backend is the single source of truth —
  // swap LITELLM_MODEL in .env and this reflects it on next load. Retried,
  // because on `just dev` this request almost always lands before uvicorn is
  // listening; without a retry the chip stays blank for the whole session.
  useEffect(() => {
    const controller = new AbortController();
    fetchJsonWithRetry<{ model?: string }>('/api/meta', { signal: controller.signal })
      .then((data) => {
        if (data?.model) setModelLabel(data.model);
      })
      .catch(() => {
        // The gate already reports unreachability; a blank model chip on top of
        // that would be noise, so this one stays quiet.
      });
    return () => controller.abort();
  }, [bootstrapNonce]);

  // Product catalogue (GET /api/products) for the scope picker and the gate.
  // Derived from the indexed docs, so a new doc + reindex makes a product
  // appear with no FE change.
  //
  // This is the request that MUST survive a slow backend: the gate is a hard
  // block on the conversation, and with an empty catalogue it renders no
  // product cards at all. Resolving to `[]` because the port was not open yet
  // is therefore not a degraded state, it is a dead end.
  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    fetchJsonWithRetry<{ products?: Product[] }>('/api/products', { signal: controller.signal })
      .then((data) => {
        if (cancelled) return;
        if (Array.isArray(data?.products)) setProducts(data.products);
        // Reached the backend. An empty list now means the index is not built —
        // a real answer, not a race, so the gate stops waiting and offers the
        // "all products" escape hatch.
        setBackendStatus('ready');
        setProductsLoading(false);
      })
      .catch((err) => {
        if (cancelled || (err instanceof DOMException && err.name === 'AbortError')) return;
        setBackendStatus('unreachable');
        setProductsLoading(false);
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [bootstrapNonce]);

  // Persist language choice across reloads.
  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('docagent.lang', lang);
    }
  }, [lang]);

  // Auto-scroll to the newest message. 'auto' (instant) while streaming so
  // rapid appends don't thrash overlapping smooth-scrolls; 'smooth' on settle.
  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: busy ? 'auto' : 'smooth' });
  }, [messages, busy]);

  // Sequence-based key per appended message so Preact diffs cheaply/correctly.
  const nextId = useRef(0);
  const withId = useCallback(
    (m: Message): Message => ({ ...m, id: m.id ?? `m${nextId.current++}` }),
    [],
  );

  async function send(overrideInput?: string) {
    const text = (overrideInput ?? input).trim();
    // The composer is disabled before the gate is passed; this guard covers the
    // other paths into send() (suggested prompts, retry) so no turn can reach
    // the backend without a scope decision behind it.
    if (!text || busy || !scopeChosen) return;

    const userMessage = withId({ role: 'user', content: text });
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

      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      for await (const { event, data } of parseSSE(res.body)) {
        if (event === 'message') {
          try {
            const msg: Message = JSON.parse(data);
            setMessages((prev) => [...prev, withId(msg)]);
          } catch {
            setMessages((prev) => [
              ...prev,
              withId({ role: 'assistant', content: copy.errorGeneric, isError: true }),
            ]);
          }
        } else if (event === 'error') {
          setMessages((prev) => [
            ...prev,
            withId({ role: 'assistant', content: mapErrorToFriendly(data, copy), isError: true }),
          ]);
        } else if (event === 'done') {
          receivedDone = true;
          if (data) setSessionId(data);
        }
      }

      // Stream closed without `done` → the connection dropped mid-flight.
      if (!receivedDone) {
        setMessages((prev) => [
          ...prev,
          withId({ role: 'assistant', content: copy.errorStreamDropped, isError: true }),
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        withId({ role: 'assistant', content: mapErrorToFriendly(String(err), copy), isError: true }),
      ]);
    } finally {
      setBusy(false);
      textareaRef.current?.focus();
    }
  }

  // Typing label: assistant message with only tool_calls = mid-retrieval;
  // otherwise it's reasoning over text.
  const typingLabel = useMemo(() => {
    const last = messages[messages.length - 1];
    if (last?.role === 'assistant' && last.tool_calls?.length && !last.content) {
      return copy.typingSearching;
    }
    return copy.typingThinking;
  }, [messages, copy]);

  return {
    messages,
    input,
    setInput,
    busy,
    lang,
    setLang,
    modelLabel,
    products,
    productsLoading,
    backendStatus,
    retryBootstrap,
    activeProductId,
    scopeChosen,
    chooseScope,
    copy,
    send,
    typingLabel,
    endOfMessagesRef,
    textareaRef,
  };
}
