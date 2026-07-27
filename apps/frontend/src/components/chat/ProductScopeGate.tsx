/**
 * ProductScopeGate — the "which product?" screen shown before the first message.
 *
 * Atomic-design role: organism. Replaces WelcomeState until a scope is chosen,
 * and the composer stays disabled behind it.
 *
 * WHY A GATE AND NOT A CHIP ROW:
 * The picker used to sit above the composer with "all products" preselected, so
 * in practice nobody ever set it and every question searched the whole corpus.
 * A filter that defaults to off is not a filter. Making the choice the first
 * thing you do turns it into a real decision — and the backend now enforces
 * whatever is picked here (graph.call_tools injects it into the search call),
 * so this screen is the actual control surface for retrieval scope.
 *
 * "All products" is still available, but as a visually separate secondary
 * action rather than the first chip in the row: it should read as an
 * intentional choice for cross-product questions, not as the easy default.
 */
import { Button } from '@/components/ui/button';
import type { Copy } from '@/lib/copy';
import type { Product } from '@/lib/chat';

type ProductScopeGateProps = {
  copy: Copy;
  products: Product[];
  loading: boolean;
  onChoose: (id: string | null) => void;
};

export function ProductScopeGate({ copy, products, loading, onChoose }: ProductScopeGateProps) {
  return (
    <div class="anim-in mt-[8vh] flex flex-col gap-5">
      <div class="border-l-[3px] border-gold pl-3">
        <h2 class="m-0 text-[1.375rem] font-semibold leading-snug tracking-[-0.02em]">
          {copy.gateHeading}
        </h2>
      </div>

      <p class="m-0 max-w-[58ch] text-[0.9375rem] leading-relaxed text-muted-foreground">
        {copy.gateSubtitle}
      </p>

      {loading ? (
        // Same card footprint as the real buttons so nothing jumps when the
        // catalogue lands. aria-hidden because the live region below carries
        // the status for assistive tech.
        <>
          <div class="grid gap-2.5 sm:grid-cols-2" aria-hidden="true">
            {[0, 1, 2, 3].map((i) => (
              <span key={i} class="h-[58px] rounded-lg bg-muted motion-safe:animate-pulse" />
            ))}
          </div>
          <span class="sr-only" role="status">
            {copy.gateLoading}
          </span>
        </>
      ) : (
        <>
          <div class="grid gap-2.5 sm:grid-cols-2">
            {products.map((p, i) => (
              <Button
                key={p.id}
                type="button"
                variant="outline"
                className="anim-in h-auto w-full justify-start rounded-lg px-4 py-3 text-left font-normal hover:border-primary"
                style={{ animationDelay: `${i * 60 + 100}ms` }}
                onClick={() => onChoose(p.id)}
              >
                <span class="flex flex-col gap-0.5">
                  <span class="text-[0.9375rem] font-medium text-foreground">{p.name}</span>
                  <span class="font-mono text-[0.6875rem] text-muted-foreground">{p.id}</span>
                </span>
              </Button>
            ))}
          </div>

          {/* Escape hatch, kept deliberately quieter than the product cards. */}
          <div class="flex flex-wrap items-center gap-2 border-t border-border pt-4">
            <Button
              type="button"
              variant="ghost"
              className="h-auto rounded-md px-3 py-1.5 text-[0.875rem] font-normal text-muted-foreground hover:text-foreground"
              onClick={() => onChoose(null)}
            >
              {copy.gateAllProducts}
            </Button>
            <span class="text-[0.75rem] text-muted-foreground">
              {copy.gateAllProductsHint}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
