/** Evidence panel — the retrieval verdict behind one assistant answer.
 *
 *  Atomic-design role: molecule. Sits between the answer body and the citation
 *  strip in MessageList's MarkdownContent.
 *
 *  WHY THIS EXISTS
 *  The backend already knew which passages it trusted and why, and none of it
 *  reached the screen. That mattered more than usual here, because on this
 *  corpus the obvious signal lies: the index is built with an English
 *  embedding model (`bge-small-en-v1.5`) over largely Indonesian docs, so
 *  measured against the real index "resep rendang padang" scores 0.514 while
 *  "gimana cara menjalankan proyek ini di lokal" scores 0.501. The off-topic
 *  question wins. Keyword overlap is what actually separates them (on topic
 *  3-10, off topic 0-1), and that is what `agent/relevance.py` gates on.
 *
 *  So the panel shows BOTH numbers, and it lists rejected passages instead of
 *  hiding them. A reader who sees a 0.51 passage skipped for zero shared words
 *  understands the ranking in one glance; a reader shown only the winners has
 *  to take it on faith.
 *
 *  Nothing here is recomputed on the client — every score, overlap and verdict
 *  comes from relevance.py over the `retrieval` SSE event. One judgement, one
 *  place.
 *
 *  Native <details>/<summary>: collapsible with no state to manage, keyboard
 *  operable and screen-reader announced for free. Closed by default so the
 *  transcript stays calm — this is for the reader who asks "says who?".
 */
import clsx from 'clsx';
import type { Confidence, Retrieval, Verdict } from '@/lib/chat';
import type { Copy } from '@/lib/copy';
import { ChevronDownIcon, LayersIcon } from './icons';

/** Badge tint per confidence level.
 *
 *  Semantic tokens rather than the maroon brand `primary`: this communicates
 *  answer *quality*, not brand, and green/gold/grey is the scale people already
 *  read that way. `none` is deliberately not `destructive` — finding nothing is
 *  an honest outcome, not a failure. */
const CONFIDENCE_STYLE: Record<Confidence, string> = {
  high: 'border-success/30 bg-success/10 text-success',
  medium: 'border-gold/40 bg-gold/10 text-gold',
  low: 'border-hairline bg-muted text-muted-foreground',
  none: 'border-hairline bg-muted text-muted-foreground',
};

/** Fill colour of the similarity bar, by verdict. */
const BAR_STYLE: Record<Verdict, string> = {
  strong: 'bg-primary',
  weak: 'bg-muted-foreground/50',
  rejected: 'bg-border',
};

export function EvidencePanel({ retrieval, copy }: { retrieval: Retrieval; copy: Copy }) {
  const { chunks, confidence, product_id: productId } = retrieval;
  if (!chunks.length) return null;

  const used = chunks.filter((c) => c.verdict === 'strong').length;

  return (
    <details class="group mt-3 overflow-hidden rounded-lg border border-hairline bg-card/60">
      <summary
        class="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-[0.75rem] transition-colors duration-200 hover:bg-accent/40 focus-visible:outline-none focus-visible:bg-accent/40"
        aria-label={copy.evidenceAria}
      >
        <LayersIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span class="font-semibold uppercase tracking-wide text-muted-foreground">
          {copy.evidenceLabel}
        </span>
        <span
          class={clsx(
            'shrink-0 rounded-full border px-2 py-[1px] text-[0.7rem] font-medium',
            CONFIDENCE_STYLE[confidence],
          )}
        >
          {copy.evidenceConfidence(confidence)}
        </span>
        {/* Pushed right and allowed to disappear first on a narrow screen — the
            confidence badge is the part that must always be readable. */}
        <span class="ml-auto hidden truncate text-muted-foreground sm:inline">
          {copy.evidenceUsed(used, chunks.length)}
        </span>
        <ChevronDownIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-200 group-open:rotate-180" />
      </summary>

      <div class="border-t border-hairline px-3 py-2.5">
        {productId && (
          <p class="mb-2 text-[0.72rem] text-muted-foreground">
            {copy.evidenceScopeNote(productId)}
          </p>
        )}
        {confidence === 'none' && (
          <p class="mb-2.5 rounded-md bg-muted px-2.5 py-2 text-[0.72rem] leading-relaxed text-muted-foreground">
            {copy.evidenceNoneNote}
          </p>
        )}
        <ul class="flex flex-col gap-2.5">
          {chunks.map((chunk, i) => (
            <li
              key={`${chunk.source}-${i}`}
              class={clsx('flex flex-col gap-1', chunk.verdict === 'rejected' && 'opacity-60')}
            >
              <div class="flex items-baseline gap-2">
                <span
                  class={clsx(
                    'min-w-0 flex-1 truncate text-[0.78rem] font-medium text-foreground',
                    // Struck through, not hidden: the skipped passage is the
                    // most instructive row in the list.
                    chunk.verdict === 'rejected' && 'line-through decoration-1',
                  )}
                  title={chunk.heading}
                >
                  {chunk.heading}
                </span>
                <span class="shrink-0 text-[0.68rem] uppercase tracking-wide text-muted-foreground">
                  {copy.evidenceVerdict(chunk.verdict)}
                </span>
              </div>

              <div class="flex items-center gap-2">
                {/* Similarity as a bar AND a number. The bar makes "these two
                    are basically the same" visible at a glance, which is the
                    whole point when the higher one is the rejected one. */}
                <div
                  class="h-1 min-w-0 flex-1 overflow-hidden rounded-full bg-sunken"
                  role="img"
                  aria-label={`${copy.evidenceScore} ${chunk.score.toFixed(2)}`}
                >
                  <div
                    class={clsx('h-full rounded-full', BAR_STYLE[chunk.verdict])}
                    style={{ width: `${Math.max(0, Math.min(1, chunk.score)) * 100}%` }}
                  />
                </div>
                <span class="shrink-0 font-mono text-[0.68rem] text-muted-foreground">
                  {chunk.score.toFixed(2)}
                </span>
                <span
                  class={clsx(
                    'shrink-0 rounded-full border px-1.5 py-[1px] text-[0.68rem]',
                    chunk.overlap === 0
                      ? 'border-hairline text-muted-foreground'
                      : 'border-primary/25 bg-primary/5 text-primary',
                  )}
                >
                  {copy.evidenceMatches(chunk.overlap)}
                </span>
              </div>

              <p
                class="truncate font-mono text-[0.68rem] text-muted-foreground"
                title={chunk.source}
              >
                {chunk.source}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </details>
  );
}
