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
import { LayersIcon } from './icons';
import type { BackendStatus } from '@/hooks/use-chat';
import type { Copy } from '@/lib/copy';
import type { Product } from '@/lib/chat';

type ProductScopeGateProps = {
  copy: Copy;
  products: Product[];
  loading: boolean;
  onChoose: (id: string | null) => void;
  /** 'connecting' keeps the skeleton up; 'unreachable' swaps in the retry
   *  panel. Without this the gate could only say "no products", which is the
   *  wrong story when the truth is "the backend has not booted yet". */
  backendStatus: BackendStatus;
  onRetryBootstrap: () => void;
};

export function ProductScopeGate({
  copy,
  products,
  loading,
  onChoose,
  backendStatus,
  onRetryBootstrap,
}: ProductScopeGateProps) {
  return (
    <div class="anim-in mt-[5vh] flex flex-col gap-5 sm:mt-[8vh]">
      <div class="relative pl-3.5">
        <span
          class="absolute inset-y-0 left-0 w-[3px] rounded-full bg-gradient-to-b from-gold to-transparent"
          aria-hidden="true"
        />
        <h2 class="m-0 text-[1.25rem] font-semibold leading-snug tracking-[-0.02em] sm:text-[1.375rem]">
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
              <span key={i} class="h-[62px] rounded-xl bg-muted motion-safe:animate-pulse" />
            ))}
            {/* Placeholder for the full-width "all products" option, so the
                block does not grow by a row when the catalogue lands. */}
            <span class="h-[62px] rounded-xl bg-muted motion-safe:animate-pulse sm:col-span-2" />
          </div>
          {/* The live region says which of the two waits this is, so it is not
              silently "loading" for 40s while the backend boots. */}
          <span class="sr-only" role="status">
            {backendStatus === 'connecting' ? copy.gateConnecting : copy.gateLoading}
          </span>
        </>
      ) : backendStatus === 'unreachable' ? (
        // Never a dead end. Retries are already exhausted by the time this
        // renders, so the only thing left is to explain and offer the button.
        <div
          class="anim-in flex flex-col items-start gap-3 rounded-xl border border-hairline border-l-[3px] border-l-warning bg-card p-4 shadow-panel"
          role="status"
        >
          <p class="m-0 text-[0.9375rem] font-medium text-foreground">
            {copy.gateUnreachableHeading}
          </p>
          <p class="m-0 max-w-[58ch] text-[0.875rem] leading-relaxed text-muted-foreground">
            {copy.gateUnreachableBody}
          </p>
          <Button
            type="button"
            variant="outline"
            className="h-auto rounded-lg border-hairline px-3.5 py-2 text-[0.875rem] font-normal hover:border-primary/50"
            onClick={onRetryBootstrap}
          >
            {copy.gateRetry}
          </Button>
        </div>
      ) : (
        <>
          <div class="grid gap-2.5 sm:grid-cols-2">
            {products.map((p, i) => (
              <Button
                key={p.id}
                type="button"
                variant="outline"
                // min-h-[62px] matches the skeleton so nothing jumps when the
                // catalogue lands, and clears the 44px touch minimum.
                className="anim-in group h-auto min-h-[62px] w-full justify-start rounded-xl border-hairline bg-card/60 px-4 py-3 text-left font-normal shadow-panel transition-all duration-200 ease-expo hover:border-primary/50 hover:bg-card hover:shadow-glow motion-safe:hover:-translate-y-0.5"
                style={{ animationDelay: `${i * 60 + 100}ms` }}
                onClick={() => onChoose(p.id)}
                // The id is the only part that can realistically outrun the
                // card, and it is the part a native tooltip helps least (it is
                // already a machine string). Title carries the full pair for
                // the rare long one; the name itself no longer truncates.
                title={`${p.name} · ${p.id}`}
              >
                {/* The name WRAPS instead of truncating. A product name is the
                    whole basis of the choice — clipping it to "Dash Participant
                    S…" forces a hover just to read the option you are being
                    asked to pick. The card has vertical room; use it. */}
                <span class="flex min-w-0 flex-col gap-0.5">
                  <span class="whitespace-normal text-[0.9375rem] font-medium leading-snug text-foreground">
                    {p.name}
                  </span>
                  <span class="truncate font-mono text-[0.6875rem] text-muted-foreground">
                    {p.id}
                  </span>
                </span>
              </Button>
            ))}
          </div>

          {/* "All products" — a real third option, not a footnote.
           *
           * It used to be a ghost button with the hint as loose text beside it,
           * below a divider. Ghost has no border and no fill, so the only thing
           * marking it as clickable was the label itself, and it read as a
           * caption rather than a choice — which is exactly the "kurang
           * noticeable" problem.
           *
           * Now it is the same card affordance as the products (icon, label,
           * description, full hit area) so it is obviously selectable, but it
           * stays subordinate through a DASHED border and no fill: same weight
           * class, visibly a different kind of choice. Spanning the full grid
           * width also stops it from reading as a fifth product. */}
          <Button
            type="button"
            variant="outline"
            className="anim-in group h-auto w-full justify-start gap-3 rounded-xl border-dashed border-border bg-transparent px-4 py-3 text-left font-normal transition-all duration-200 ease-expo hover:border-solid hover:border-primary/50 hover:bg-card/60 hover:shadow-panel"
            style={{ animationDelay: `${products.length * 60 + 140}ms` }}
            onClick={() => onChoose(null)}
          >
            <span
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-hairline bg-card text-muted-foreground transition-colors duration-200 group-hover:border-primary/30 group-hover:text-primary"
              aria-hidden="true"
            >
              <LayersIcon className="h-[18px] w-[18px]" />
            </span>
            <span class="flex min-w-0 flex-col gap-0.5">
              <span class="whitespace-normal text-[0.9375rem] font-medium leading-snug text-foreground">
                {copy.gateAllProducts}
              </span>
              <span class="whitespace-normal text-[0.75rem] leading-snug text-muted-foreground">
                {copy.gateAllProductsHint}
              </span>
            </span>
          </Button>
        </>
      )}
    </div>
  );
}
