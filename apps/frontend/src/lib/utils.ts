/**
 * cn() — the className combiner used by every shadcn-style component.
 *
 * `clsx` resolves conditional/array class inputs into one string; `tailwind-merge`
 * then dedupes conflicting Tailwind utilities so the LAST one wins (e.g.
 * `cn('px-2', 'px-4')` → `px-4`). That dedupe is what lets a component expose a
 * `className` prop that cleanly overrides its own defaults.
 */
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
