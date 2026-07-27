/**
 * ChatHeader — the top bar of the chat shell.
 *
 * Atomic-design role: organism. Composes four smaller pieces:
 *   • the brand mark (document glyph on a maroon tile) + app title
 *   • the ProductScopePicker (active retrieval scope, once the gate is passed)
 *   • the model chip (plain metadata text, sourced from GET /api/meta)
 *   • the LanguageToggle molecule (ID/EN segmented control)
 *
 * The scope picker lives here rather than above the composer because it is now
 * persistent conversation state, not a per-message option: the gate sets it and
 * the header is where you see and change it.
 *
 * Keeping the header isolated means Chat.tsx never needs to know what goes in
 * the bar — it just renders <ChatHeader … />. Every color references a token
 * from global.css @theme (bg-background, bg-primary, text-muted-foreground…),
 * never a raw hex.
 */
import { LanguageToggle } from './LanguageToggle';
import { ProductScopePicker } from './ProductScopePicker';
import { DocumentIcon } from './icons';
import type { Copy, Language } from '@/lib/copy';
import type { Product } from '@/lib/chat';

type ChatHeaderProps = {
  copy: Copy;
  lang: Language;
  onLangChange: (next: Language) => void;
  modelLabel: string;
  products: Product[];
  activeProductId: string | null;
  onScopeChange: (id: string | null) => void;
  scopeChosen: boolean;
};

export function ChatHeader({
  copy,
  lang,
  onLangChange,
  modelLabel,
  products,
  activeProductId,
  onScopeChange,
  scopeChosen,
}: ChatHeaderProps) {
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

      <div class="flex shrink-0 items-center gap-2.5">
        <ProductScopePicker
          copy={copy}
          products={products}
          activeProductId={activeProductId}
          onSelect={onScopeChange}
          visible={scopeChosen}
        />

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
