/** Right-aligned user message bubble (pale-maroon tint).
 *
 *  The outer row carries AssistantRow's GUTTER as right padding so the user
 *  side is inset by exactly the width the avatar occupies on the assistant
 *  side. That is the whole symmetry fix: previously assistant text started 42px
 *  from the left while user bubbles ended 0px from the right, so the transcript
 *  looked lopsided no matter how the bubbles themselves were styled.
 *
 *  The asymmetric corner (rounded-br-md against rounded-2xl elsewhere) points
 *  the bubble at its own side of the column, which distinguishes it from the
 *  assistant's flush-left text without needing a second fill colour.
 *
 *  RESPONSIVE: 85% on a phone, 72% from sm up — a flat 72% wasted a quarter of
 *  a 360px viewport on what is usually one short line.
 *
 *  overflow-wrap-anywhere: a pasted URL or an unspaced token would otherwise
 *  push the bubble past its max-width and scroll the whole transcript sideways. */
import { GUTTER } from './AssistantRow';

export function UserBubble({ content }: { content: string }) {
  return (
    <div class={`anim-in flex w-full justify-end ${GUTTER}`}>
      <div class="max-w-[85%] rounded-2xl rounded-br-md border border-primary/10 bg-primary-soft px-4 py-2.5 text-[0.9375rem] leading-relaxed text-foreground shadow-panel [overflow-wrap:anywhere] sm:max-w-[72%] sm:px-[18px] sm:py-3">
        {content}
      </div>
    </div>
  );
}
