/** Citation strip — displayed below an assistant answer that cited its sources.
 *
 *  The main-agent prompt instructs the LLM to end grounded answers with a
 *  "Sources:" list. `extractCitations` (lib/chat.ts) parses those out of the
 *  raw content before markdown rendering.
 *
 *  TWO KINDS OF SOURCE, both rendered.
 *  This used to filter to `URL_RE` and drop everything else, which quietly made
 *  the whole feature invisible: our knowledge base is local markdown, so nearly
 *  every citation the agent emits is a repo-relative path like
 *  `docs/knowledge-base/tep-cms.md` — and with those discarded the strip had
 *  nothing left to draw. A path is not clickable (there is no URL to open), so
 *  it renders as a static chip rather than a link, but "here is the file"
 *  is exactly what someone reading a documentation answer needs.
 *
 *  Returns null only when there are no citations at all, so calling code can
 *  pass citations unconditionally and the strip vanishes when not needed.
 */
import type { Copy } from '@/lib/copy';
import { DocumentIcon } from './icons';

const URL_RE = /^https?:\/\/.+/;

type CitationListProps = {
  citations: string[];
  copy: Copy;
};

/**
 * Split a URL into the two parts worth showing in a chip.
 *
 * Printing the raw href and clipping it with `truncate` was the worst possible
 * choice here: every doc URL from the same site shares a long prefix, so a row
 * of truncated chips all read "https://docs.example.com/gui…" — identical, and
 * distinguishable only by hovering each one. Leading with the host and then the
 * LAST path segment puts the part that actually differs in front of the user.
 *
 * Falls back to the raw string if the URL will not parse, so a malformed
 * citation still renders instead of throwing inside the transcript.
 */
function splitCitation(raw: string): { host: string; tail: string } {
  try {
    const url = new URL(raw);
    const segments = url.pathname.split('/').filter(Boolean);
    const last = segments[segments.length - 1] ?? '';
    return {
      host: url.hostname.replace(/^www\./, ''),
      // decodeURIComponent so a percent-encoded segment reads as words.
      tail: last ? decodeURIComponent(last) : '',
    };
  } catch {
    return { host: raw, tail: '' };
  }
}

/** Split a file path the same way `splitCitation` splits a URL: the part that
 *  locates it, then the part that identifies it. Sources from one product all
 *  share a directory, so leading with the basename would be as ambiguous as
 *  leading with the host was for URLs — the directory goes first, dimmed. */
function splitPath(raw: string): { dir: string; name: string } {
  const segments = raw.split(/[\\/]/).filter(Boolean);
  const name = segments.pop() ?? raw;
  return { dir: segments.length ? segments[segments.length - 1] : '', name };
}

/** Shared chip shell so a link and a plain path sit on the same visual line. */
const CHIP =
  'inline-flex max-w-full items-center gap-1.5 rounded-md border border-hairline bg-card px-2.5 py-1 text-[0.75rem] shadow-panel';

export function CitationList({ citations, copy }: CitationListProps) {
  if (!citations.length) return null;

  return (
    <div class="mt-3 border-t border-hairline pt-3">
      <p class="mb-1.5 text-[0.7rem] font-semibold uppercase tracking-wide text-muted-foreground">
        {copy.citationSources}
      </p>
      <ul class="flex flex-wrap gap-1.5">
        {citations.map((src, i) => (
          <li key={i} class="min-w-0 max-w-full">
            {URL_RE.test(src) ? <UrlChip src={src} /> : <PathChip src={src} />}
          </li>
        ))}
      </ul>
    </div>
  );
}

function UrlChip({ src }: { src: string }) {
  const { host, tail } = splitCitation(src);
  return (
    /* bg-card, not bg-surface: `surface` is not a token in @theme, so the old
       class compiled to nothing and left these chips transparent against the
       transcript.
       title = the full href. A native tooltip is not reachable by keyboard or
       touch, so it is the fallback for the rare long tail, never the way the
       chip is meant to be read — the host and tail below are chosen so it
       usually is not needed. */
    <a
      href={src}
      target="_blank"
      rel="noopener noreferrer"
      title={src}
      class={`${CHIP} transition-all duration-200 ease-expo hover:border-primary/40 hover:bg-primary/5 hover:shadow-raised focus-visible:outline-none focus-visible:border-ring focus-visible:shadow-glow`}
    >
      <LinkIcon />
      <span class="shrink-0 font-mono text-muted-foreground">{host}</span>
      {tail && (
        <>
          <span class="shrink-0 text-muted-foreground/50" aria-hidden="true">
            /
          </span>
          {/* Only the tail is allowed to truncate, and it is the part that
              varies — so a clipped chip still tells you which page it is. */}
          <span class="min-w-0 truncate font-medium text-primary">{tail}</span>
        </>
      )}
    </a>
  );
}

/** A repo-relative source file. Not a link — there is nothing to navigate to —
 *  so it is a <span>, not an <a> with a dead href. */
function PathChip({ src }: { src: string }) {
  const { dir, name } = splitPath(src);
  return (
    <span title={src} class={CHIP}>
      <DocumentIcon className="h-3 w-3 shrink-0 text-muted-foreground" />
      {dir && (
        <>
          <span class="shrink-0 font-mono text-muted-foreground">{dir}</span>
          <span class="shrink-0 text-muted-foreground/50" aria-hidden="true">
            /
          </span>
        </>
      )}
      <span class="min-w-0 truncate font-mono font-medium text-foreground">{name}</span>
    </span>
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
