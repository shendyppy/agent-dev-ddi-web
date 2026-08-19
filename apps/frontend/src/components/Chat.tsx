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
import ModalInputBaseKnowledge from './ui/ModalInputBaseKnowledge';
import { API_BASE } from '@/lib/chat';
import { notification } from 'antd';

export default function Chat() {
  const auth = useAuth();
  const chat = useChat(auth.user);
  const history = useHistory(auth.user);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const showModal = () => {
    setIsModalOpen(true);
  };

  const handleOk = async (
    filename: string,
    productId: string,
    productName: string,
    content: string,
  ) => {
    if (!filename || !productId || !productName || !content) {
      notification.warning({
        title: 'Peringatan',
        description: 'Semua isian tidak boleh kosong!',
      });
      return;
    }

    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/knowledge-base`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          filename,
          product_id: productId,
          product_name: productName,
          content,
        }),
      });

      if (!res.ok) {
        // Surface the server's own message rather than one generic string. The
        // failures the user can actually act on are distinct: 409 = that
        // filename is taken, 422 = the document did not parse, 500/504 = it
        // was saved but not indexed. A single "Gagal" toast told them none of
        // that, so the only recovery on offer was to retype and retry.
        const detail = await res
          .json()
          .then((body) => (typeof body?.detail === 'string' ? body.detail : null))
          .catch(() => null);
        throw new Error(detail ?? `Gagal menyimpan knowledge base (HTTP ${res.status})`);
      }

      notification.success({
        title: 'Berhasil',
        description: 'Knowledge base berhasil disimpan!',
      });
      setIsModalOpen(false);

      // 'just index' is now synchronous on the backend, so we can fetch immediately
      chat.retryBootstrap();
    } catch (e) {
      console.error(e);
      notification.error({
        title: 'Gagal',
        description: e instanceof Error ? e.message : 'Gagal menyimpan knowledge base!',
        // Server messages are a sentence or two, not a few words; the default
        // auto-dismiss is too short to read one.
        duration: 10,
      });
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

        <ModalInputBaseKnowledge
          isModalOpen={isModalOpen}
          isSaving={isSaving}
          handleOk={handleOk}
          handleCancel={handleCancel}
        />

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
