/**
 * ProductScopePicker — the "Fokus:" chip row that soft-scopes the agent to one
 * product's docs.
 *
 * Atomic-design role: molecule. Three states, all derived from the catalogue
 * fetch in useChat:
 *   • loading === true          → pulsing skeleton chips. Same height/shape as
 *                                 the real chips, so swapping them in causes no
 *                                 layout jump. This is the fix for "the focus
 *                                 row pops in after products load" — now there's
 *                                 a clear loading affordance instead of nothing.
 *   • settled + list empty      → null (no products indexed / backend down), so
 *                                 Chat.tsx renders nothing and the row collapses.
 *   • settled + list ≥ 1        → the real chip group. Selection is expressed
 *                                 with aria-pressed (toggle-group semantics) so
 *                                 assistive tech announces "selected".
 *
 * Every chip gets the same gentle active:scale press as ui/Button, gated behind
 * prefers-reduced-motion via motion-safe:.
 */
import { cn } from '@/lib/utils';
import type { Copy } from '@/lib/copy';
import type { Product } from '@/lib/chat';

type ProductScopePickerProps = {
  copy: Copy;
  products: Product[];
  activeProductId: string | null;
  onSelect: (id: string | null) => void;
  loading: boolean;
};

export function ProductScopePicker({
  copy,
  products,
  activeProductId,
  onSelect,
  loading,
}: ProductScopePickerProps) {
  // Fetch settled and nothing came back → nothing to focus on, hide the row.
  if (!loading && products.length === 0) return null;

  const chipClass = (active: boolean) =>
    cn(
      'cursor-pointer rounded-full border px-3 py-1 text-[0.75rem] transition-all duration-150 motion-safe:active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
      active
        ? 'border-primary bg-primary text-primary-foreground'
        : 'border-border bg-muted text-muted-foreground hover:border-primary hover:text-foreground',
    );

  return (
    <div
      class="flex w-full max-w-[760px] flex-wrap items-center gap-2.5"
      role="group"
      aria-label={copy.productScopeAria}
    >
      <span class="shrink-0 text-[0.75rem] font-medium text-muted-foreground">
        {copy.productScopeLabel}
      </span>

      {loading ? (
        // Skeleton chips — purely decorative, so aria-hidden. The real chips
        // arrive within a moment and carry the accessible labels. Pulse is
        // wrapped in motion-safe: to match how the typing dots in global.css
        // behave under prefers-reduced-motion (static, not animated).
        <div class="flex flex-wrap gap-1.5" aria-hidden="true">
          <span class="h-[26px] w-[92px] rounded-full bg-muted motion-safe:animate-pulse" />
          <span class="h-[26px] w-[64px] rounded-full bg-muted motion-safe:animate-pulse" />
          <span class="h-[26px] w-[78px] rounded-full bg-muted motion-safe:animate-pulse" />
        </div>
      ) : (
        <div class="flex flex-wrap gap-1.5">
          <button
            type="button"
            class={chipClass(activeProductId === null)}
            aria-pressed={activeProductId === null}
            onClick={() => onSelect(null)}
          >
            {copy.productScopeAll}
          </button>

          {products.map((p) => (
            <button
              key={p.id}
              type="button"
              class={chipClass(activeProductId === p.id)}
              aria-pressed={activeProductId === p.id}
              onClick={() => onSelect(p.id)}
              title={p.name}
            >
              {p.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
