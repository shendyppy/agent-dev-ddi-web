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
import { ProductScopePicker } from './chat/ProductScopePicker';
import { ChatComposer } from './chat/ChatComposer';

export default function Chat() {
  const chat = useChat();

  return (
    <div class="flex h-screen flex-col overflow-hidden bg-background font-sans text-foreground">
      <ChatHeader
        copy={chat.copy}
        lang={chat.lang}
        onLangChange={chat.setLang}
        modelLabel={chat.modelLabel}
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
      />

      <footer class="flex w-full flex-col items-center gap-2.5 border-t border-border bg-background px-6 pb-6 pt-4">
        <ProductScopePicker
          copy={chat.copy}
          products={chat.products}
          activeProductId={chat.activeProductId}
          onSelect={chat.setActiveProductId}
          loading={chat.productsLoading}
        />
        <ChatComposer
          copy={chat.copy}
          value={chat.input}
          onChange={chat.setInput}
          onSubmit={() => chat.send()}
          busy={chat.busy}
          textareaRef={chat.textareaRef}
        />
      </footer>
    </div>
  );
}
