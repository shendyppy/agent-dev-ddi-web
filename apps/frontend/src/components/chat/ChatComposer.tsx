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
import type { Ref } from "preact";
import { useState, useEffect } from "preact/hooks";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { SendIcon, MicIcon } from "./icons";
import type { Copy } from "@/lib/copy";

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
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      const rec = new SpeechRecognition();
      rec.continuous = true; // Diubah ke true agar tidak langsung mati saat jeda pendek
      rec.lang = "id-ID";
      rec.interimResults = true; // Kita aktifkan interim dengan manajemen state yang baik

      rec.onstart = () => setIsListening(true);
      rec.onend = () => setIsListening(false);

      rec.onresult = (event: any) => {
        let finalTranscript = "";
        let interimTranscript = "";

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
        const fullText =
          finalTranscript + (interimTranscript ? " " + interimTranscript : "");

        if (fullText.trim()) {
          onChange(fullText);
        }
      };

      rec.onerror = (event: any) => {
        console.error("Speech error", event.error);
        setIsListening(false);
      };

      setRecognition(rec);
    }
  }, []);

  const toggleListening = () => {
    if (!recognition) {
      alert("Browser Anda tidak mendukung Voice Input.");
      return;
    }

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
    target.style.height = "auto";
    target.style.height = `${Math.min(target.scrollHeight, 200)}px`;
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
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
        placeholder={locked ? copy.composerLockedPlaceholder : copy.inputPlaceholder}
        aria-label={copy.inputLabel}
        disabled={busy || locked}
        rows={1}
      />
      {/* BUTTON 1: VOICE INPUT (Symmetric 40px Circle) */}
      {recognition && (
        <Button
          type="button"
          size="icon"
          className={`h-10 w-10 shrink-0 rounded-full transition duration-200 active:scale-95 disabled:opacity-40 ${
            isListening
              ? "bg-red-500 text-white hover:bg-red-600 animate-pulse"
              : "hover:bg-accent hover:text-accent-foreground"
          }`}
          onClick={toggleListening}
          disabled={busy || locked}
          title="Voice Input"
          aria-label="Voice Input"
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
