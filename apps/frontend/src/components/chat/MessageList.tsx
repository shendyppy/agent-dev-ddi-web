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
import { CitationList } from './CitationList';
import { renderMarkdown, extractCitations, type Message } from '@/lib/chat';
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
                  <MarkdownContent content={m.content as string} copy={copy} />
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
