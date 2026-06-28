/**
 * ChatHeader — the top bar of the chat shell.
 *
 * Atomic-design role: organism. Composes three smaller pieces:
 *   • the brand mark (document glyph on a maroon tile) + app title
 *   • the model chip (plain metadata text, sourced from GET /api/meta)
 *   • the LanguageToggle molecule (ID/EN segmented control)
 *
 * Keeping the header isolated means Chat.tsx never needs to know what goes in
 * the bar — it just renders <ChatHeader … />. Every color references a token
 * from global.css @theme (bg-background, bg-primary, text-muted-foreground…),
 * never a raw hex.
 */
import { LanguageToggle } from './LanguageToggle';
import { DocumentIcon } from './icons';
import type { Copy, Language } from '@/lib/copy';

type ChatHeaderProps = {
  copy: Copy;
  lang: Language;
  onLangChange: (next: Language) => void;
  modelLabel: string;
};

export function ChatHeader({ copy, lang, onLangChange, modelLabel }: ChatHeaderProps) {
  return (
    <header class="z-10 flex items-center justify-between gap-4 border-b border-border bg-background px-6 py-3">
      <div class="flex min-w-0 items-center gap-2.5">
        {/* Document glyph on a maroon tile — deliberately not a star/sparkle,
            which reads as a generic AI product. */}
        <span
          class="inline-flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-sm bg-primary text-primary-foreground"
          aria-hidden="true"
        >
          <DocumentIcon className="h-[14px] w-[14px]" />
        </span>
        <h1 class="m-0 truncate text-[0.9375rem] font-semibold tracking-[-0.01em]">
          {copy.appTitle}
        </h1>
      </div>

      <div class="flex shrink-0 items-center gap-2">
        {/* Model chip — plain mono text with no pill border, so it reads as
            metadata rather than a control. Stays empty until /api/meta
            resolves, then shows whatever LITELLM_MODEL the backend is on. */}
        <span
          class="font-mono text-[0.6875rem] text-muted-foreground"
          title={modelLabel ? `Model: ${modelLabel}` : 'Model: …'}
        >
          {modelLabel || '…'}
        </span>
        <LanguageToggle lang={lang} onChange={onLangChange} copy={copy} />
      </div>
    </header>
  );
}
