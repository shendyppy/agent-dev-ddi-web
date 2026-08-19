/**
 * Chat island — the Preact component hydrated on every page via `client:only`.
 *
 * After the atomic-design split this file is just a thin shell/template: it
 * pulls all state + side effects out of `useChat()` and wires the returned
 * values into the three regions of the layout — header, transcript, composer.
 * Every visual is a dedicated molecule under components/chat/*, each built on
 * the shadcn-style atoms in components/ui/*. Behaviour (SSE streaming, markdown
 * sanitising, friendly-error mapping) lives in lib/chat.ts + hooks/use-chat.ts,
 * so this component has no fetch, no SSE parser, and no string wrangling.
 *
 * Colours reference Tailwind v4 @theme tokens (bg-background, text-foreground,
 * bg-primary, border-border…) defined in src/styles/global.css from the Odyssey
 * brand palette (near-black ink, deep-maroon primary, warm gold accent,
 * cool-light surfaces).
 */
import { useState } from 'preact/hooks';
import { useChat } from '@/hooks/use-chat';
import { useAuth } from '@/hooks/use-auth';
import { useHistory } from '@/hooks/use-history';
import { ChatHeader } from './chat/ChatHeader';
import { MessageList } from './chat/MessageList';
import { ChatComposer } from './chat/ChatComposer';
import { HistoryPanel } from './chat/HistoryPanel';
import { KnowledgeBaseModal, DRAFT_KEY } from './chat/KnowledgeBaseModal';
import { API_BASE } from '@/lib/chat';

export default function Chat() {
  const auth = useAuth();
  const chat = useChat(auth.user);
  const history = useHistory(auth.user);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [kbError, setKbError] = useState<string | null>(null);
  const [kbSubmitted, setKbSubmitted] = useState(false);

  const showModal = () => {
    setKbError(null);
    setIsModalOpen(true);
  };

  const handleKbSubmit = async (draft: {
    title: string;
    productId: string;
    productName: string;
    body: string;
  }) => {
    setIsSaving(true);
    setKbError(null);
    try {
      // The write endpoint requires a verified session — the button being
      // visible is not authorisation. Fetch the token at submit time rather
      // than caching it, because Supabase refreshes it in the background.
      const token = await auth.getAccessToken();
      if (!token) {
        throw new Error(chat.copy.errorPrefix);
      }

      const res = await fetch(`${API_BASE}/api/knowledge-base`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          filename: draft.title,
          product_id: draft.productId,
          product_name: draft.productName,
          content: draft.body,
        }),
      });

      if (!res.ok) {
        // Surface the server's own message rather than one generic string. The
        // failures the user can act on are distinct: 401/403 = sign in or ask
        // for access, 409 = that filename is taken, 422 = the document did not
        // validate. A single "Gagal" toast told them none of that, so the only
        // recovery on offer was to retype and retry.
        const detail = await res
          .json()
          .then((body) => (typeof body?.detail === 'string' ? body.detail : null))
          .catch(() => null);
        throw new Error(detail ?? `${chat.copy.kbErrorTitle} (HTTP ${res.status})`);
      }

      // The draft exists to survive an accidental close, not a successful
      // submit — keeping it would repopulate the form with a document that is
      // already in the queue.
      window.localStorage.removeItem(DRAFT_KEY);
      setIsModalOpen(false);
      setKbSubmitted(true);
      window.setTimeout(() => setKbSubmitted(false), 6000);
    } catch (e) {
      console.error(e);
      setKbError(e instanceof Error ? e.message : chat.copy.kbErrorTitle);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setIsModalOpen(false);
  };

  return (
    // h-dvh, not h-screen: on mobile browsers the URL bar shrinks the visual
    // viewport, and `100vh` keeps reporting the *unshrunk* height — so the
    // composer used to sit below the fold behind the address bar. `h-screen`
    // stays as the preceding declaration for engines without dvh support.
    <div class="app-shell flex h-screen h-dvh overflow-hidden font-sans text-foreground">
      {/* Desktop layout spacer — pushes main content as panel slides in */}
      <div
        class={`hidden sm:block shrink-0 transition-[width] duration-250 ease-in-out ${historyOpen ? 'w-64' : 'w-0'}`}
      />

      <HistoryPanel
        copy={chat.copy}
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        sessions={history.sessions}
        loading={history.loading}
        activeSessionId={activeSessionId}
        onSelectSession={async (s) => {
          const msgs = await history.loadMessages(s.id);
          chat.loadSession(msgs, s.product_scope, s.id);
          setActiveSessionId(s.id);
          setHistoryOpen(false);
        }}
        onNewChat={() => {
          chat.newChat();
          setActiveSessionId(null);
          setHistoryOpen(false);
        }}
      />

      <div class="flex flex-1 flex-col overflow-hidden">
        <ChatHeader
          copy={chat.copy}
          lang={chat.lang}
          onLangChange={chat.setLang}
          products={chat.products}
          activeProductId={chat.activeProductId}
          onScopeChange={chat.chooseScope}
          scopeChosen={chat.scopeChosen}
          user={auth.user}
          onLogin={auth.login}
          onLogout={() => {
            auth.logout();
            chat.newChat();
            setActiveSessionId(null);
            setHistoryOpen(false);
          }}
          onHistoryToggle={() => setHistoryOpen((o) => !o)}
          models={chat.models}
          modelsLoading={chat.modelsLoading}
          modelsFailed={chat.modelsFailed}
          onRetryModels={chat.retryBootstrap}
          modelId={chat.modelId}
          onModelChange={chat.setModelId}
          apiKey={chat.apiKey}
          onApiKeyChange={chat.setApiKey}
          offlineMode={chat.offlineMode}
          onOfflineModeChange={chat.setOfflineMode}
          showModal={showModal}
        />

        <MessageList
          copy={chat.copy}
          messages={chat.messages}
          busy={chat.busy}
          typingLabel={chat.typingLabel}
          endOfMessagesRef={chat.endOfMessagesRef}
          onPickPrompt={(p) => {
            chat.setInput(p);
            chat.textareaRef.current?.focus();
          }}
          // Retry re-sends the last user turn. If there is none (edge case) send()
          // no-ops on the empty string.
          onRetry={() =>
            chat.send(chat.messages.filter((m) => m.role === 'user').slice(-1)[0]?.content ?? '')
          }
          products={chat.products}
          productsLoading={chat.productsLoading}
          scopeChosen={chat.scopeChosen}
          onChooseScope={chat.chooseScope}
          backendStatus={chat.backendStatus}
          onRetryBootstrap={chat.retryBootstrap}
        />

        <KnowledgeBaseModal
          copy={chat.copy}
          open={isModalOpen}
          saving={isSaving}
          products={chat.products}
          productsLoading={chat.productsLoading}
          error={kbError}
          onSubmit={handleKbSubmit}
          onClose={handleCancel}
        />

        {/* Confirmation lives outside the modal because the modal closes on
          success — a toast inside it would never be seen. */}
        {kbSubmitted && (
          <div
            role="status"
            class="fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-lg border border-border bg-card px-4 py-2.5 shadow-lg"
          >
            <p class="text-sm font-medium">{chat.copy.kbSuccessTitle}</p>
            <p class="text-xs text-muted-foreground">{chat.copy.kbSuccessBody}</p>
          </div>
        )}

        {/* Translucent + blurred so the transcript visibly passes *under* the
          composer as it scrolls, which is what sells the layering. The border
          is an edge-fade rule rather than a full-bleed border-t.
          pb uses safe-area-inset so the bar clears the iOS home indicator. */}
        <footer class="edge-fade edge-fade--top z-10 flex w-full flex-col items-center gap-2.5 bg-background/80 px-4 pt-3 backdrop-blur-xl sm:px-6 sm:pt-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:pb-6">
          <ChatComposer
            copy={chat.copy}
            value={chat.input}
            onChange={chat.setInput}
            onSubmit={() => chat.send()}
            busy={chat.busy}
            textareaRef={chat.textareaRef}
            enabled={chat.scopeChosen}
          />
        </footer>
      </div>
    </div>
  );
}
