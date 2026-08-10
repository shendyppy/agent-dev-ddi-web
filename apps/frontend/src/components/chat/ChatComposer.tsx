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
import { useState, useEffect } from 'preact/hooks';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { SendIcon, MicIcon } from './icons';
import type { Copy } from '@/lib/copy';

type ChatComposerProps = {
  copy: Copy;
  value: string;
  onChange: (next: string) => void;
  onSubmit: () => void;
  busy: boolean;
  textareaRef: Ref<HTMLTextAreaElement>;
  /** False until the product scope gate has been passed. */
  enabled: boolean;
};

export function ChatComposer({
  copy,
  value,
  onChange,
  onSubmit,
  busy,
  textareaRef,
  enabled,
}: ChatComposerProps) {
  // --- VOICE INPUT STATE & LOGIC ---
  const [isListening, setIsListening] = useState(false);
  const [recognition, setRecognition] = useState<any>(null);

  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      const rec = new SpeechRecognition();
      rec.continuous = true; // Diubah ke true agar tidak langsung mati saat jeda pendek
      rec.lang = 'id-ID';
      rec.interimResults = true; // Kita aktifkan interim dengan manajemen state yang baik

      rec.onstart = () => setIsListening(true);
      rec.onend = () => setIsListening(false);

      rec.onresult = (event: any) => {
        let finalTranscript = '';
        let interimTranscript = '';

        // Loop semua hasil dari awal sampai akhir sesi speech saat ini
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }

        // Gabungkan teks yang sudah final dengan yang masih ditebak (interim)
        // Trik smooth: Berikan spasi tipis jika keduanya ada
        const fullText = finalTranscript + (interimTranscript ? ' ' + interimTranscript : '');

        if (fullText.trim()) {
          onChange(fullText);
        }
      };

      rec.onerror = (event: any) => {
        console.error('Speech error', event.error);
        setIsListening(false);
      };

      setRecognition(rec);
    }
  }, []);

  // The button is only rendered when `recognition` is non-null, so there is no
  // unsupported-browser branch to handle here.
  const toggleListening = () => {
    if (!recognition) return;

    if (isListening) {
      recognition.stop();
    } else {
      recognition.start();
    }
  };
  // --- END OF VOICE INPUT LOGIC ---

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

  // `locked` covers "no scope picked yet"; `busy` covers "a turn is in flight".
  // Both disable input, but only the former changes the placeholder — it is the
  // one the user can act on, and the placeholder is where we say how.
  const locked = !enabled;
  const canSend = enabled && !busy && value.trim().length > 0;

  return (
    // rounded-2xl + shadow-sm softens the box; focus-within swaps to the maroon
    // ring token and lifts the surface so the active field is unambiguous.
    // rounded-2xl + shadow-raised lifts the field off the blurred footer;
    // focus-within swaps the ambient shadow for the brand glow so the active
    // field is unambiguous without adding a second ring on top of the border.
    <div class="anim-in flex w-full max-w-[760px] items-end gap-1.5 rounded-2xl border border-hairline bg-card px-2 py-2 shadow-raised transition-all duration-300 ease-expo focus-within:border-ring focus-within:shadow-glow sm:gap-2 sm:px-2.5">
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
        placeholder={locked ? copy.composerLockedPlaceholder : copy.inputPlaceholder}
        aria-label={copy.inputLabel}
        disabled={busy || locked}
        rows={1}
      />
      {/* BUTTON 1: VOICE INPUT (Symmetric 40px Circle)
          variant="ghost", not the default fill: the mic previously inherited
          `bg-primary` and sat next to an identically maroon send button, so the
          composer had two competing primary actions. Ghost makes send the only
          filled control. The listening state now uses the destructive token
          rather than a hardcoded palette red, which was off brand and did not
          respond to dark mode.

          NOTE: do not name a Tailwind class literally in a comment — the v4
          scanner reads raw file text, so a class mentioned in prose is still
          emitted into the bundle as dead CSS.
          aria-pressed exposes the on/off state that the colour alone conveys. */}
      {recognition && (
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className={`h-10 w-10 shrink-0 rounded-full transition-all duration-200 ease-expo disabled:opacity-40 ${
            isListening
              ? 'bg-destructive text-destructive-foreground shadow-glow hover:bg-destructive/90 motion-safe:animate-pulse'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'
          }`}
          onClick={toggleListening}
          disabled={busy || locked}
          title={isListening ? copy.voiceStopLabel : copy.voiceLabel}
          aria-label={isListening ? copy.voiceStopLabel : copy.voiceLabel}
          aria-pressed={isListening}
        >
          <MicIcon className="h-[18px] w-[18px]" />
        </Button>
      )}

      {/* BUTTON 2: SEND */}
      <Button
        type="button"
        size="icon"
        // h-10 w-10 keeps the button the same height as a single-line textarea;
        // rounded-full + hover/active scale give it presence and a tactile feel.
        // `transition` (all) wins over the variant's transition-colors so the
        // transform animates too.
        className="tile-sheen h-10 w-10 shrink-0 rounded-full shadow-panel ring-1 ring-inset ring-white/15 transition-all duration-200 ease-expo hover:shadow-glow motion-safe:hover:scale-[1.06] disabled:opacity-40 disabled:shadow-none"
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
