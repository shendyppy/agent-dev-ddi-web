/**
 * Inline SVG icons used across the chat UI.
 *
 * Deliberately a plain document sheet and simple glyphs — NOT a star / sparkle,
 * which reads as a generic AI product. All icons inherit `currentColor` and
 * take a className for sizing so they compose with Tailwind utilities.
 */
type IconProps = { className?: string };

const base = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  'stroke-width': '2',
  'stroke-linecap': 'round' as const,
  'stroke-linejoin': 'round' as const,
  'aria-hidden': 'true' as const,
};

/**
 * DocumentIcon — the brand mark (header tile + assistant avatar).
 *
 * FILLED, not stroked. The previous version was a 2px-stroke outline on a
 * 24-unit viewBox, rendered at 15px. That scales the stroke down to ~1.25 CSS
 * px, which lands on a fractional device pixel and renders as a grey, fuzzy
 * scribble — worst of all on the maroon header tile, where a hairline outline
 * has almost nothing to hold onto. A filled silhouette keeps its shape at any
 * size because there is no stroke to shrink.
 *
 * It was also mis-centred: the old path spanned x 4→20 in a 24 box, so the
 * glyph sat 1 unit left of centre inside the tile. This one spans x 5→19 and
 * y 2→22 — even margins on both axes.
 *
 * Single path with fill-rule="evenodd": the two inner rectangles are subpaths,
 * so they punch through as knocked-out text lines instead of needing separate
 * background-coloured shapes (which would break on any tile colour).
 */
export const DocumentIcon = ({ className }: IconProps) => (
  <svg class={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path
      fill-rule="evenodd"
      clip-rule="evenodd"
      d="M7 2h7v4.5A1.5 1.5 0 0 0 15.5 8H19v12a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm1 10h8v1.7H8V12Zm0 3.6h5.5v1.7H8v-1.7Z"
    />
    {/* The folded corner, carried at reduced opacity so the fold reads as a
        crease rather than a second solid mass competing with the body. */}
    <path d="M15 2.4 18.9 6.6H16.2A1.2 1.2 0 0 1 15 5.4V2.4Z" opacity="0.55" />
  </svg>
);

/** Concentric rings — marks the active retrieval scope ("focus"). */
export const TargetIcon = ({ className }: IconProps) => (
  <svg class={className} {...base}>
    <circle cx="12" cy="12" r="8" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

/** Disclosure chevron for the scope pill. */
export const ChevronDownIcon = ({ className }: IconProps) => (
  <svg class={className} {...base}>
    <path d="m6 9 6 6 6-6" />
  </svg>
);

/** Stacked planes — marks the "all products" (cross-product) scope option. */
export const LayersIcon = ({ className }: IconProps) => (
  <svg class={className} {...base}>
    <path d="M12 3 3 8l9 5 9-5-9-5Z" />
    <path d="M3 13l9 5 9-5" />
  </svg>
);

/** Circled "i" — marks supplementary help text on a compact control.
 *
 *  Takes `title` and renders it as an SVG `<title>` child rather than a `title`
 *  attribute. Same hover tooltip, but it also becomes the element's accessible
 *  name, so a screen reader reads the explanation instead of announcing an
 *  unlabelled graphic. `aria-hidden` is dropped here for the same reason — this
 *  icon carries information, unlike the decorative ones above. */
export const InfoIcon = ({ className, title }: IconProps & { title?: string }) => (
  <svg
    class={className}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    role={title ? 'img' : undefined}
    aria-hidden={title ? undefined : 'true'}
  >
    {title && <title>{title}</title>}
    <circle cx="12" cy="12" r="9" />
    <path d="M12 16v-5" />
    <path d="M12 8h.01" />
  </svg>
);

export const SearchIcon = ({ className }: IconProps) => (
  <svg class={className} {...base}>
    <circle cx="11" cy="11" r="7" />
    <path d="M21 21l-4.3-4.3" />
  </svg>
);

export const CheckIcon = ({ className }: IconProps) => (
  <svg class={className} {...base}>
    <path d="M20 6L9 17l-5-5" />
  </svg>
);

export const SendIcon = ({ className }: IconProps) => (
  <svg class={className} {...base}>
    <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
  </svg>
);

export const MicIcon = ({ className }: IconProps) => (
  <svg class={className} {...base}>
    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
    <path d="M19 10v1a7 7 0 0 1-14 0v-1" />
    <line x1="12" x2="12" y1="19" y2="22" />
  </svg>
);
