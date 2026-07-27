/**
 * ProductScopePicker — the "Fokus: X" control in the header.
 *
 * Atomic-design role: molecule. This used to be a chip row above the composer
 * with "all products" preselected, which meant the scope was almost never set.
 * The initial choice now happens at the gate (ProductScopeGate); this control's
 * only job is showing the active scope and letting the user change it
 * mid-conversation without losing the transcript.
 *
 * A native <select> rather than a custom popover: it is one of the few controls
 * browsers already make fully keyboard- and screen-reader-accessible, and it
 * collapses to a single line in a dense header. The visible chrome comes from
 * the wrapper, so it inherits the same tokens as the rest of the bar.
 *
 * Renders nothing before the gate is passed — there is no scope to display yet.
 */
import type { Copy } from '@/lib/copy';
import type { Product } from '@/lib/chat';

type ProductScopePickerProps = {
  copy: Copy;
  products: Product[];
  activeProductId: string | null;
  onSelect: (id: string | null) => void;
  visible: boolean;
};

// Sentinel for "all products" — <option> values are always strings, so null
// needs a stand-in that cannot collide with a real product id.
const ALL = '__all__';

export function ProductScopePicker({
  copy,
  products,
  activeProductId,
  onSelect,
  visible,
}: ProductScopePickerProps) {
  if (!visible) return null;

  return (
    <label class="flex min-w-0 items-center gap-1.5">
      <span class="shrink-0 text-[0.6875rem] text-muted-foreground">
        {copy.productScopeLabel}
      </span>
      <select
        class="max-w-[180px] cursor-pointer truncate rounded-md border border-border bg-muted px-2 py-1 text-[0.75rem] text-foreground transition-colors hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background"
        value={activeProductId ?? ALL}
        aria-label={copy.scopeChangeAria}
        onChange={(e) => {
          const next = (e.target as HTMLSelectElement).value;
          onSelect(next === ALL ? null : next);
        }}
      >
        {products.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
        <option value={ALL}>{copy.productScopeAll}</option>
      </select>
    </label>
  );
}
