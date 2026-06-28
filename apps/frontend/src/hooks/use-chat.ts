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
  parseSSE,
  mapErrorToFriendly,
  type Message,
  type Product,
} from '@/lib/chat';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [lang, setLang] = useState<Language>(loadInitialLang);
  const [modelLabel, setModelLabel] = useState('');
  const [products, setProducts] = useState<Product[]>([]);
  // True until the first /api/products round-trip settles (success OR failure).
  // Drives the skeleton in ProductScopePicker so the "Fokus:" row doesn't pop in
  // after load — it pulses while waiting, then either shows the chips or hides.
  const [productsLoading, setProductsLoading] = useState(true);
  const [activeProductId, setActiveProductId] = useState<string | null>(null);

  const endOfMessagesRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const copy = COPY[lang];

  // Active model label (GET /api/meta). Backend is the single source of truth —
  // swap LITELLM_MODEL in .env and this reflects it on next load.
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/meta`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data?.model) setModelLabel(data.model);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Product catalogue (GET /api/products) for the scope picker. Derived from
  // the indexed docs, so a new doc + reindex makes a product appear with no FE
  // change. While the fetch is in flight, productsLoading stays true so the
  // picker shows a skeleton; once it settles, an empty list (index not built /
  // backend down) hides the picker entirely.
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/products`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && Array.isArray(data?.products)) setProducts(data.products);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setProductsLoading(false);
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
    if (!text || busy) return;

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
    activeProductId,
    setActiveProductId,
    copy,
    send,
    typingLabel,
    endOfMessagesRef,
    textareaRef,
  };
}
