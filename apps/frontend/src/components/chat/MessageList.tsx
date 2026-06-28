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
import { AssistantRow } from './AssistantRow';
import { UserBubble } from './UserBubble';
import { ToolChip } from './ToolChip';
import { TypingIndicator } from './TypingIndicator';
import { ErrorBubble } from './ErrorBubble';
import { renderMarkdown, type Message } from '@/lib/chat';
import type { Copy } from '@/lib/copy';

type MessageListProps = {
  copy: Copy;
  messages: Message[];
  busy: boolean;
  typingLabel: string;
  endOfMessagesRef: Ref<HTMLDivElement>;
  onPickPrompt: (prompt: string) => void;
  onRetry: () => void;
};

/** Markdown body for an assistant message.
 *
 *  `renderMarkdown` (lib/chat.ts) is memoised by content string and runs the
 *  output through DOMPurify, so this is safe to inject. The `.markdown-body`
 *  hook class is styled in global.css — Tailwind utilities can't reach into
 *  nodes created via dangerouslySetInnerHTML at scan time. */
function MarkdownContent({ content }: { content: string }) {
  return (
    <div
      class="markdown-body text-[1rem] leading-relaxed text-foreground"
      dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
    />
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
}: MessageListProps) {
  return (
    <div class="flex flex-1 flex-col items-center overflow-y-auto px-6 py-6">
      <div
        class="flex w-full max-w-[760px] flex-col gap-5 pb-10"
        role="log"
        aria-live="polite"
        aria-atomic="false"
        aria-label={copy.chatLogLabel}
      >
        {messages.length === 0 ? (
          <WelcomeState copy={copy} onPickPrompt={onPickPrompt} />
        ) : (
          messages.map((m) => {
            if (m.role === 'user') {
              return <UserBubble key={m.id} content={m.content ?? ''} />;
            }

            if (m.role === 'tool') {
              return (
                <AssistantRow key={m.id}>
                  <ToolChip kind="result" label={copy.toolResult(m.content?.length ?? 0)} />
                </AssistantRow>
              );
            }

            // assistant
            const hasContent = (m.content ?? '').trim().length > 0;
            const hasToolCalls = !!m.tool_calls?.length;
            if (!hasContent && !hasToolCalls) return null;

            return (
              <AssistantRow key={m.id}>
                {m.isError ? (
                  <ErrorBubble content={m.content ?? ''} copy={copy} onRetry={onRetry} />
                ) : hasContent ? (
                  <MarkdownContent content={m.content as string} />
                ) : (
                  <ToolChip kind="calling" label={copy.toolCalling} />
                )}
              </AssistantRow>
            );
          })
        )}

        {busy && (
          <AssistantRow>
            <TypingIndicator label={typingLabel} />
          </AssistantRow>
        )}

        {/* Scroll sentinel — useChat scrolls this into view on new messages. */}
        <div ref={endOfMessagesRef} />
      </div>
    </div>
  );
}
