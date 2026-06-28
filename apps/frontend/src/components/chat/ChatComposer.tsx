/**
 * ChatComposer — the message input box + send button.
 *
 * Atomic-design role: molecule. Composes the ui/Textarea and ui/Button atoms
 * inside a single bordered, focus-aware container.
 *
 * WHY THE SEND BUTTON IS A 40px CIRCLE (the symmetry fix):
 * The previous monolith used a 36px square button against an asymmetrically
 * padded textarea, so the button looked un-centered and visually weak. Here
 * the textarea's single-line box is sized to exactly match the button —
 * leading-6 line height + py-2 vertical padding = 40px = Button h-10 — and the
 * button is a circle (rounded-full) so it reads as symmetric regardless of the
 * paper-plane icon's optical mass. `items-end` then gives perfect centering at
 * one line and pins the button to the bottom-right as the textarea grows. The
 * icon gets a 1px rightward nudge because a send glyph points up-right, so its
 * optical centre sits slightly right of its geometric centre.
 *
 * Owns the two input-only behaviours so they stay out of Chat.tsx:
 *   • handleInput  — controlled value + auto-grow up to max-h-[200px]
 *   • handleKeyDown — Enter sends, Shift+Enter inserts a newline
 */
import type { Ref } from 'preact';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { SendIcon } from './icons';
import type { Copy } from '@/lib/copy';

type ChatComposerProps = {
  copy: Copy;
  value: string;
  onChange: (next: string) => void;
  onSubmit: () => void;
  busy: boolean;
  textareaRef: Ref<HTMLTextAreaElement>;
};

export function ChatComposer({
  copy,
  value,
  onChange,
  onSubmit,
  busy,
  textareaRef,
}: ChatComposerProps) {
  const handleInput = (e: Event) => {
    const target = e.target as HTMLTextAreaElement;
    onChange(target.value);
    // Auto-grow to fit content, capped at 200px; beyond that it scrolls.
    target.style.height = 'auto';
    target.style.height = `${Math.min(target.scrollHeight, 200)}px`;
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  const canSend = !busy && value.trim().length > 0;

  return (
    // rounded-2xl + shadow-sm softens the box; focus-within swaps to the maroon
    // ring token and lifts the surface so the active field is unambiguous.
    <div class="anim-in flex w-full max-w-[760px] items-end gap-2 rounded-2xl border border-border bg-card px-2.5 py-2 shadow-sm transition-all duration-200 focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/20">
      <label class="sr-only" htmlFor="chat-input">
        {copy.inputLabel}
      </label>

      <Textarea
        ref={textareaRef}
        id="chat-input"
        className="min-h-[40px] max-h-[200px] flex-1 px-2 py-2 leading-6"
        value={value}
        onInput={handleInput}
        onKeyDown={handleKeyDown}
        placeholder={copy.inputPlaceholder}
        aria-label={copy.inputLabel}
        disabled={busy}
        rows={1}
      />

      <Button
        type="button"
        size="icon"
        // h-10 w-10 keeps the button the same height as a single-line textarea;
        // rounded-full + hover/active scale give it presence and a tactile feel.
        // `transition` (all) wins over the variant's transition-colors so the
        // transform animates too.
        className="h-10 w-10 shrink-0 rounded-full transition duration-200 hover:scale-[1.05] hover:bg-primary/90 active:scale-95 disabled:opacity-40"
        onClick={onSubmit}
        disabled={!canSend}
        title={copy.sendLabel}
        aria-label={copy.sendAria}
      >
        {/* translate-x-px: optical nudge for the up-right-pointing glyph. */}
        <SendIcon className="h-[18px] w-[18px]" />
      </Button>
    </div>
  );
}
