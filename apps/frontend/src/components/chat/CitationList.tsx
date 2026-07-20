/** Citation strip — displayed below an assistant answer when the LLM cited URLs.
 *
 *  The main-agent prompt instructs the LLM to end grounded answers with a
 *  "Sources:" list. `extractCitations` (lib/chat.ts) parses those out of the
 *  raw content before markdown rendering. This component filters to show ONLY
 *  URLs (not file paths) — when the user asks for links/URLs, they get
 *  clickable sources directly from the knowledge base.
 *
 *  Returns null if there are no URLs in the citations, so calling code can
 *  pass citations unconditionally and the strip vanishes when not needed.
 */
import type { Copy } from '@/lib/copy';

const URL_RE = /^https?:\/\/.+/;

type CitationListProps = {
  citations: string[];
  copy: Copy;
};

export function CitationList({ citations, copy }: CitationListProps) {
  // Filter to only URLs from knowledge base
  const urlCitations = citations.filter((src) => URL_RE.test(src));

  // Only render if there are actual URLs to show
  if (!urlCitations.length) return null;

  return (
    <div class="mt-3 border-t border-border pt-3">
      <p class="mb-1.5 text-[0.7rem] font-semibold uppercase tracking-wide text-muted-foreground">
        {copy.citationSources}
      </p>
      <ul class="flex flex-wrap gap-1.5">
        {urlCitations.map((src, i) => (
          <li key={i}>
            <a
              href={src}
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center gap-1.5 rounded border border-border bg-surface px-2.5 py-1 font-mono text-[0.75rem] text-primary hover:bg-primary/10 hover:underline transition-colors"
            >
              <LinkIcon />
              <span class="truncate max-w-xs">{src}</span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function LinkIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
      class="flex-shrink-0"
    >
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  );
}
