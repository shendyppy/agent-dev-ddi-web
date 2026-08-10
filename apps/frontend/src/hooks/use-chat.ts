/**
 * useChat — all chat state + side effects in one hook.
 *
 * Pulling this out of the component keeps Chat.tsx a thin layout/template:
 * it just wires the returned values into the header / message list / composer.
 * Owns: message list, input, busy flag, session id, language, model label,
 * product catalogue + active scope, and the send() round-trip (fetch + SSE).
 */
import { useState, useRef, useEffect, useMemo, useCallback } from 'preact/hooks';
import type { User } from '@supabase/supabase-js';
import { COPY, loadInitialLang, type Language } from '@/lib/copy';
import {
  API_BASE,
  fetchJsonWithRetry,
  parseSSE,
  mapErrorToFriendly,
  modelHeaders,
  loadStoredApiKey,
  storeApiKey,
  loadStoredModelId,
  storeModelId,
  loadStoredOffline,
  storeOffline,
  type Message,
  type ModelCatalogue,
  type ModelOption,
  type Product,
  type Retrieval,
} from '@/lib/chat';
import { supabase } from '@/lib/supabase';

/** Keep last 20 turns; truncate long assistant responses to 1 000 chars so the
 *  context window stays manageable when continuing from saved history. */
function compressHistory(msgs: Message[]): { role: string; content: string }[] {
  const ASSISTANT_MAX = 1000;
  const WINDOW = 20;
  return msgs
    .filter((m) => m.role === 'user' || (m.role === 'assistant' && m.content))
    .slice(-WINDOW)
    .map((m) => ({
      role: m.role,
      content:
        m.role === 'assistant' && (m.content?.length ?? 0) > ASSISTANT_MAX
          ? m.content!.slice(0, ASSISTANT_MAX) + '…'
          : (m.content ?? ''),
    }));
}

async function saveHistory(
  userId: string,
  sessionId: string | null,
  productScope: string | null,
  newMessages: Message[],
) {
  // Nothing to persist to. Callers already treat history as fire-and-forget,
  // so returning quietly is the correct degradation.
  if (!supabase) return;

  const { data: session, error: sessionErr } = await supabase
    .from('chat_sessions')
    .upsert({ id: sessionId ?? undefined, user_id: userId, product_scope: productScope })
    .select('id')
    .single();
  if (sessionErr || !session) return;

  if (!newMessages.length) return;

  await supabase
    .from('chat_messages')
    .insert(
      newMessages.map((m) => ({ session_id: session.id, role: m.role, content: m.content ?? '' })),
    );
}

/** Bootstrap connectivity, surfaced so the gate can explain itself instead of
 *  rendering as an empty, dead screen while the backend is still booting. */
export type BackendStatus = 'connecting' | 'ready' | 'unreachable';

/** How long to wait after the last keystroke before re-fetching the catalogue.
 *
 *  400ms is the usual "they stopped typing" threshold — long enough that a
 *  paste or a fast typist produces one request, short enough that the list does
 *  not feel stuck after the field settles. */
const MODELS_DEBOUNCE_MS = 400;

export function useChat(user: User | null = null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [lang, setLang] = useState<Language>(loadInitialLang);
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
  // Model choice + the user's own provider key (BYOK, ADR 0010). Both are read
  // from localStorage on mount so a reload keeps the user's setup, and the key
  // never travels anywhere except the X-Model-Api-Key header.
  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsFailed, setModelsFailed] = useState(false);
  const [modelId, setModelIdState] = useState<string>(loadStoredModelId);
  const [apiKey, setApiKeyState] = useState<string>(loadStoredApiKey);

  const setModelId = useCallback((id: string) => {
    setModelIdState(id);
    storeModelId(id);
  }, []);

  const setApiKey = useCallback((key: string) => {
    setApiKeyState(key);
    storeApiKey(key);
  }, []);

  // Answer from the local index without calling the provider. Per request, not
  // process-wide — see llm.acompletion. Persisted so a reload keeps the choice,
  // which is the point: it exists so offline mode is checkable at a glance
  // instead of being an env var you have to go and read.
  const [offlineMode, setOfflineModeState] = useState<boolean>(loadStoredOffline);
  const setOfflineMode = useCallback((on: boolean) => {
    setOfflineModeState(on);
    storeOffline(on);
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

  // The /api/meta fetch that used to live here is gone: it existed only to fill
  // a read-only model chip, and /api/models now returns the same deployment
  // default alongside the catalogue the picker needs. One request instead of
  // two, and no second source of truth about which model is active.

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

  // Model catalogue (GET /api/models). Re-fetched when the key changes, because
  // availability is resolved against that key server-side — pasting a key should
  // update the list without a reload.
  //
  // DEBOUNCED, and that is not a polish detail. `apiKey` updates on every
  // keystroke, so the first version of this effect fired one request per
  // character: pasting a 60-character key meant 60 requests, each carrying a
  // partial credential, and the responses could land out of order and leave the
  // list describing a prefix of the key rather than the whole thing. The delay
  // means the request happens once the typing stops.
  //
  // The key goes in a header here too, never a query parameter: a URL ends up in
  // access logs and browser history.
  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    setModelsLoading(true);

    const timer = setTimeout(() => {
      // fetchJsonWithRetry, not a bare fetch: `just dev` starts the frontend
      // and backend together and the frontend always wins the race, so the
      // first attempt routinely lands on a closed port. Swallowing that left
      // `models` empty forever, and an empty list made ModelPicker render
      // nothing at all — the control vanished from the header with no
      // explanation. Same failure the product catalogue already had, so it gets
      // the same fix rather than a second hand-rolled one.
      fetchJsonWithRetry<ModelCatalogue>('/api/models', {
        signal: controller.signal,
        headers: modelHeaders('', apiKey),
        // Fewer attempts than the product catalogue (12). That one is a hard
        // block — no products means no conversation — so it is worth waiting
        // ~45s for. This one is not: chat works fine on the configured default
        // without the picker, so giving up after ~10s and offering a retry
        // beats a control that spins for the better part of a minute.
        maxAttempts: 5,
      })
        .then((data) => {
          if (cancelled) return;
          setModels(data.models);
          setModelsFailed(false);
          // Fall back to the deployment's configured model when the user has not
          // chosen, or chose one that has since left the catalogue.
          setModelIdState((current) =>
            current && data.models.some((m) => m.id === current) ? current : data.default,
          );
        })
        .catch((err) => {
          if (cancelled || (err instanceof DOMException && err.name === 'AbortError')) return;
          // Reported, not swallowed. The picker renders a retry instead of
          // disappearing, so "the model control is gone" can never be the whole
          // story the user gets.
          setModelsFailed(true);
        })
        .finally(() => {
          if (!cancelled) setModelsLoading(false);
        });
    }, MODELS_DEBOUNCE_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      controller.abort();
    };
  }, [bootstrapNonce, apiKey]);

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
    const agentMessages: Message[] = [];
    // Evidence arrives from the `tools` node, the answer it explains from the
    // `llm` node after it — so the payload has to be parked until a message
    // with actual prose shows up, then attached to that one. A local (not a
    // ref) because its whole life is this one request.
    let pendingRetrieval: Retrieval | null = null;

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        // Model + key ride as headers, deliberately. The body below is the
        // shape `saveHistory` persists to Supabase, so a credential placed in
        // it could reach that table on any future refactor. See ADR 0010.
        headers: {
          'Content-Type': 'application/json',
          ...modelHeaders(modelId, apiKey, offlineMode),
        },
        body: JSON.stringify({
          messages: compressHistory(historyForRequest),
          session_id: sessionId,
          product_id: activeProductId,
        }),
      });

      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      for await (const { event, data } of parseSSE(res.body)) {
        if (event === 'message') {
          try {
            const msg: Message = JSON.parse(data);
            if (msg.role === 'assistant' && msg.content) {
              // Hand the parked evidence to the first answer that follows it,
              // and clear it so a second answer in the same turn does not
              // inherit the previous search's passages.
              if (pendingRetrieval) {
                msg.retrieval = pendingRetrieval;
                pendingRetrieval = null;
              }
              agentMessages.push(msg);
            }
            setMessages((prev) => [...prev, withId(msg)]);
          } catch {
            setMessages((prev) => [
              ...prev,
              withId({ role: 'assistant', content: copy.errorGeneric, isError: true }),
            ]);
          }
        } else if (event === 'retrieval') {
          // A malformed frame costs the panel, never the answer.
          try {
            pendingRetrieval = JSON.parse(data) as Retrieval;
          } catch {
            pendingRetrieval = null;
          }
        } else if (event === 'error') {
          setMessages((prev) => [
            ...prev,
            withId({ role: 'assistant', content: mapErrorToFriendly(data, copy), isError: true }),
          ]);
        } else if (event === 'done') {
          receivedDone = true;
          if (data) setSessionId(data);
          if (user) {
            // fire-and-forget: history failure must not affect the chat UX
            saveHistory(user.id, data || null, activeProductId, [
              userMessage,
              ...agentMessages,
            ]).catch(() => {});
          }
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
        withId({
          role: 'assistant',
          content: mapErrorToFriendly(String(err), copy),
          isError: true,
        }),
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
    products,
    productsLoading,
    backendStatus,
    retryBootstrap,
    activeProductId,
    scopeChosen,
    chooseScope,
    models,
    modelsLoading,
    modelsFailed,
    modelId,
    setModelId,
    apiKey,
    setApiKey,
    offlineMode,
    setOfflineMode,
    copy,
    send,
    typingLabel,
    endOfMessagesRef,
    textareaRef,
    loadSession(msgs: Message[], productId: string | null, sid: string) {
      setMessages(msgs.map(withId));
      setSessionId(sid);
      if (productId !== undefined) {
        setActiveProductId(productId);
        setScopeChosen(true);
      }
    },
    newChat() {
      setMessages([]);
      setSessionId(null);
      setScopeChosen(false);
      setActiveProductId(null);
    },
  };
}
