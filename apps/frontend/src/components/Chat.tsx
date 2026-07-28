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
import { useChat } from '@/hooks/use-chat';
import { ChatHeader } from './chat/ChatHeader';
import { MessageList } from './chat/MessageList';
import { ChatComposer } from './chat/ChatComposer';

export default function Chat() {
  const chat = useChat();

  return (
    // h-dvh, not h-screen: on mobile browsers the URL bar shrinks the visual
    // viewport, and `100vh` keeps reporting the *unshrunk* height — so the
    // composer used to sit below the fold behind the address bar. `h-screen`
    // stays as the preceding declaration for engines without dvh support.
    <div class="app-shell flex h-screen h-dvh flex-col overflow-hidden font-sans text-foreground">
      <ChatHeader
        copy={chat.copy}
        lang={chat.lang}
        onLangChange={chat.setLang}
        modelLabel={chat.modelLabel}
        products={chat.products}
        activeProductId={chat.activeProductId}
        onScopeChange={chat.chooseScope}
        scopeChosen={chat.scopeChosen}
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
  );
}
