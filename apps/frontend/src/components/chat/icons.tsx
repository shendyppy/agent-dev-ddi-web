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

export const DocumentIcon = ({ className }: IconProps) => (
  <svg class={className} {...base}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
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
