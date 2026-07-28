/**
 * MessageList — the chat transcript region (role="log", aria-live="polite").
 *
 * Atomic-design role: organism. Owns the scrolling transcript and decides which
 * molecule each wire message renders as:
 *
 *   user       → UserBubble              (right-aligned, pale-maroon)
 *   tool       → AssistantRow + ToolChip(result)
 *   assistant  → AssistantRow + one of:
 *                  ErrorBubble      (when isError)
 *                  MarkdownContent  (when it has text)
 *                  ToolChip(calling)(when it only carries tool_calls)
 *
 * A TypingIndicator is appended while a turn is in flight. The sentinel
 * `endOfMessagesRef` is what useChat's auto-scroll effect targets.
 */
import type { Ref } from 'preact';
import { WelcomeState } from './WelcomeState';
import { ProductScopeGate } from './ProductScopeGate';
import { AssistantRow } from './AssistantRow';
import { UserBubble } from './UserBubble';
import { ToolChip } from './ToolChip';
import { TypingIndicator } from './TypingIndicator';
import { ErrorBubble } from './ErrorBubble';
import { CitationList } from './CitationList';
import { renderMarkdown, extractCitations, type Message, type Product } from '@/lib/chat';
import type { BackendStatus } from '@/hooks/use-chat';
import type { Copy } from '@/lib/copy';

type MessageListProps = {
  copy: Copy;
  messages: Message[];
  busy: boolean;
  typingLabel: string;
  endOfMessagesRef: Ref<HTMLDivElement>;
  onPickPrompt: (prompt: string) => void;
  onRetry: () => void;
  // Empty-state gating: before a scope is chosen the region shows the product
  // gate instead of the welcome hero, so the first thing asked of the user is
  // the choice that scopes every later answer.
  products: Product[];
  productsLoading: boolean;
  scopeChosen: boolean;
  onChooseScope: (id: string | null) => void;
  backendStatus: BackendStatus;
  onRetryBootstrap: () => void;
};

/** Markdown body for an assistant message with an optional citation strip.
 *
 *  `extractCitations` strips the "Sources:" block from the raw content before
 *  passing it to `renderMarkdown`, then `CitationList` renders the sources in a
 *  dedicated, styled strip below the answer. Both steps are safe to call on
 *  every render because `renderMarkdown` is memoised and `extractCitations` is
 *  a cheap regex. */
function MarkdownContent({ content, copy }: { content: string; copy: Copy }) {
  const { body, citations } = extractCitations(content);
  return (
    <div class="flex flex-col">
      <div
        class="markdown-body text-[1rem] leading-relaxed text-foreground"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(body) }}
      />
      <CitationList citations={citations} copy={copy} />
    </div>
  );
}

export function MessageList({
  copy,
  messages,
  busy,
  typingLabel,
  endOfMessagesRef,
  onPickPrompt,
  onRetry,
  products,
  productsLoading,
  scopeChosen,
  onChooseScope,
  backendStatus,
  onRetryBootstrap,
}: MessageListProps) {
  // An assistant message with no text and no tool_calls has nothing to draw —
  // it is a streaming placeholder. Dropping it up front keeps the grouping and
  // spacing logic below honest about what the previous visible row actually is.
  const visibleMessages = messages.filter(
    (m) =>
      m.role !== 'assistant' ||
      (m.content ?? '').trim().length > 0 ||
      !!m.tool_calls?.length,
  );
  // Must be false on an empty transcript: `undefined !== 'user'` would be true
  // and would hide the avatar on the very first typing indicator.
  const lastIsAssistant =
    visibleMessages.length > 0 && visibleMessages[visibleMessages.length - 1].role !== 'user';

  return (
    <div class="flex flex-1 flex-col items-center overflow-y-auto px-4 py-5 sm:px-6 sm:py-6">
      {/* No `gap` on this column: spacing is per-row so a grouped follow-up can
          sit tighter (mt-2) than a genuine turn change (mt-5). A uniform gap
          made an answer plus its two tool chips look like three separate
          replies. */}
      <div
        class="flex w-full max-w-[760px] flex-col pb-10"
        role="log"
        aria-live="polite"
        aria-atomic="false"
        aria-label={copy.chatLogLabel}
      >
        {!scopeChosen ? (
          <ProductScopeGate
            copy={copy}
            products={products}
            loading={productsLoading}
            onChoose={onChooseScope}
            backendStatus={backendStatus}
            onRetryBootstrap={onRetryBootstrap}
          />
        ) : messages.length === 0 ? (
          <WelcomeState copy={copy} onPickPrompt={onPickPrompt} />
        ) : (
          // Filter BEFORE mapping: grouping and spacing depend on the previous
          // *rendered* row, and an assistant message carrying neither text nor
          // tool_calls renders nothing. Deciding that inside the map would make
          // a skipped message still count as the predecessor, so a real reply
          // after it would be treated as a grouped follow-up.
          visibleMessages.map((m, i) => {
            const prev = visibleMessages[i - 1];
            // Both 'assistant' and 'tool' render on the assistant side.
            const grouped = !!prev && prev.role !== 'user' && m.role !== 'user';
            const spacing = i === 0 ? '' : grouped ? 'mt-2' : 'mt-5';

            if (m.role === 'user') {
              return (
                <div key={m.id} class={spacing}>
                  <UserBubble content={m.content ?? ''} />
                </div>
              );
            }

            if (m.role === 'tool') {
              return (
                <div key={m.id} class={spacing}>
                  <AssistantRow grouped={grouped}>
                    <ToolChip kind="result" label={copy.toolResult(m.content?.length ?? 0)} />
                  </AssistantRow>
                </div>
              );
            }

            const hasContent = (m.content ?? '').trim().length > 0;

            return (
              <div key={m.id} class={spacing}>
                <AssistantRow grouped={grouped}>
                  {m.isError ? (
                    <ErrorBubble content={m.content ?? ''} copy={copy} onRetry={onRetry} />
                  ) : hasContent ? (
                    <MarkdownContent content={m.content as string} copy={copy} />
                  ) : (
                    <ToolChip kind="calling" label={copy.toolCalling} />
                  )}
                </AssistantRow>
              </div>
            );
          })
        )}

        {busy && (
          // Grouped whenever the transcript already ends on the assistant side,
          // so the indicator continues the current reply instead of stamping a
          // second avatar directly beneath the first.
          <div class={visibleMessages.length === 0 ? '' : lastIsAssistant ? 'mt-2' : 'mt-5'}>
            <AssistantRow streaming grouped={lastIsAssistant}>
              <TypingIndicator label={typingLabel} />
            </AssistantRow>
          </div>
        )}

        {/* Scroll sentinel — useChat scrolls this into view on new messages. */}
        <div ref={endOfMessagesRef} />
      </div>
    </div>
  );
}
