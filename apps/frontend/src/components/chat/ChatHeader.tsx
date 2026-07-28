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
    // RESPONSIVE: the bar is a single wrapping flex row, not two fixed columns.
    // Below 640px the scope picker is pushed to its own full-width second row
    // (`order-last w-full`) while brand + language toggle stay on row one; from
    // sm up everything collapses back into one line. Wrapping one element beats
    // rendering the picker twice — a duplicated <select> would mean two
    // controls with the same accessible name in the tab order.
    //
    // sticky + translucent + blur keeps the bar readable while the transcript
    // scrolls beneath it, and edge-fade replaces the full-bleed border-b that
    // made the header read as a detached box.
    <header class="edge-fade sticky top-0 z-20 flex flex-wrap items-center gap-x-3 gap-y-2 bg-background/80 px-4 py-2.5 backdrop-blur-xl sm:flex-nowrap sm:justify-between sm:gap-4 sm:px-6 sm:py-3">
      <div class="flex min-w-0 flex-1 items-center gap-2.5">
        {/* Document glyph on a maroon tile — deliberately not a star/sparkle,
            which reads as a generic AI product. The sheen + ring turn the flat
            swatch into a lit surface. */}
        <span
          class="tile-sheen inline-flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-panel ring-1 ring-inset ring-white/15"
          aria-hidden="true"
        >
          <DocumentIcon className="h-4 w-4" />
        </span>
        <h1 class="m-0 truncate text-[0.9375rem] font-semibold tracking-[-0.01em]">
          {copy.appTitle}
        </h1>
      </div>

      {/* order-last + basis-full: second row on mobile, inline from sm up. */}
      <ProductScopePicker
        copy={copy}
        products={products}
        activeProductId={activeProductId}
        onSelect={onScopeChange}
        visible={scopeChosen}
        className="order-last w-full basis-full sm:order-none sm:w-auto sm:basis-auto"
      />

      <div class="flex shrink-0 items-center gap-2.5">
        {/* Model chip — plain mono text with no pill border, so it reads as
            metadata rather than a control. Hidden below md: it is diagnostic
            info, and it is the first thing worth sacrificing for room on a
            phone. Stays empty until /api/meta resolves. */}
        <span
          class="hidden font-mono text-[0.6875rem] text-muted-foreground md:inline"
          title={modelLabel ? `Model: ${modelLabel}` : 'Model: …'}
        >
          {modelLabel || '…'}
        </span>
        <LanguageToggle lang={lang} onChange={onLangChange} copy={copy} />
      </div>
    </header>
  );
}
