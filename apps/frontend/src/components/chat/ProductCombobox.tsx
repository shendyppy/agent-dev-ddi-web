/**
 * Pick a product for a knowledge-base document — or define a new one.
 *
 * WHY THIS IS NOT A NATIVE <select>
 * The first version of the submission form used one. It fixed the *closed*
 * state and nothing else: the popup a native select opens is drawn by the OS,
 * outside the page, so it keeps system fonts, hard corners and an instant
 * appearance no CSS of ours can reach. Next to the rest of this UI it reads as
 * a different application. Same reasoning ProductScopePicker records for the
 * header control; the visual language here follows ModelPicker, which is the
 * dropdown in this app that already looks right.
 *
 * WHY IT CAN CREATE PRODUCTS
 * Products are not a table — they are derived from `product_id` in the indexed
 * documents (see `indexing._infer_product_id` and the `list_products` skill).
 * So "add a product" has always really meant "write the first document for a
 * product_id nobody has used yet", and the old form let you do that by typing
 * a free-text id. That is exactly how the corpus ended up with `klob mobile`
 * and `learning hub mobile`: ids with spaces, unusable as filters, invisible
 * to anyone trying to reference them from a test.
 *
 * So creating stays possible, but stops being accidental. You choose from what
 * exists, or you deliberately create — and when you create, the id is derived
 * for you, shown, validated against the same kebab-case rule the server
 * enforces, and checked against the ids already in use.
 *
 * Native <details>/<summary>: collapsible with no open-state to manage,
 * keyboard operable and screen-reader announced for free. Same choice
 * ModelPicker makes, for the same reason.
 */
import { useMemo, useRef, useState } from 'preact/hooks';
import clsx from 'clsx';
import type { Product } from '@/lib/chat';
import type { Copy } from '@/lib/copy';
import { ChevronDownIcon, SearchIcon, CheckIcon } from './icons';

/** What the form ends up with. `new` products do not exist server-side yet. */
export type ProductChoice = {
  id: string;
  name: string;
  isNew: boolean;
};

/** Mirrors `doc_validation.PRODUCT_ID_PATTERN` on the backend. */
export const PRODUCT_ID_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

/** Derive a kebab-case id from a display name, the way a human would. */
export function slugifyProductId(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

type ProductComboboxProps = {
  copy: Copy;
  products: Product[];
  loading: boolean;
  value: ProductChoice | null;
  onChange: (choice: ProductChoice | null) => void;
  /** Show the empty-field error. Set only after a submit attempt. */
  invalid?: boolean;
};

export function ProductCombobox({
  copy,
  products,
  loading,
  value,
  onChange,
  invalid = false,
}: ProductComboboxProps) {
  const [query, setQuery] = useState('');
  const detailsRef = useRef<HTMLDetailsElement>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return products;
    // Match on id as well as name: the id is what appears in citations and in
    // eval fixtures, so someone who knows `dash-admin-saas` should find it
    // without knowing the display name reads "DASH Admin SaaS (…)".
    return products.filter(
      (p) => p.id.toLowerCase().includes(q) || p.name.toLowerCase().includes(q),
    );
  }, [products, query]);

  const trimmedQuery = query.trim();
  // Only offer creation when the text does not already name something. Two
  // ways to end up with the same product is how duplicates get made.
  const exactMatch = products.some(
    (p) =>
      p.name.toLowerCase() === trimmedQuery.toLowerCase() ||
      p.id.toLowerCase() === trimmedQuery.toLowerCase(),
  );
  const canCreate = trimmedQuery.length > 0 && !exactMatch;

  function close() {
    if (detailsRef.current) detailsRef.current.open = false;
  }

  function chooseExisting(product: Product) {
    onChange({ id: product.id, name: product.name, isNew: false });
    setQuery('');
    close();
  }

  function chooseNew() {
    onChange({ id: slugifyProductId(trimmedQuery), name: trimmedQuery, isNew: true });
    setQuery('');
    close();
  }

  // Validation for the editable id, only meaningful while creating.
  const idTaken = Boolean(value?.isNew) && products.some((p) => p.id === value?.id);
  const idMalformed = Boolean(value?.isNew) && !PRODUCT_ID_PATTERN.test(value?.id ?? '');

  return (
    <div>
      <details ref={detailsRef} class="group relative">
        <summary
          class={clsx(
            'flex cursor-pointer list-none items-center justify-between gap-2 rounded-md border bg-background px-3 py-2 text-sm',
            'transition-all duration-200 ease-expo hover:border-primary/40',
            'focus-visible:border-ring focus-visible:outline-none',
            invalid && !value ? 'border-destructive' : 'border-border',
          )}
          aria-label={copy.kbProduct}
        >
          {value ? (
            <span class="flex min-w-0 items-center gap-2">
              <span class="truncate">{value.name}</span>
              {value.isNew && (
                <span class="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[0.65rem] font-medium text-primary">
                  {copy.kbProductNewBadge}
                </span>
              )}
            </span>
          ) : (
            <span class="text-muted-foreground">
              {loading ? copy.kbProductLoading : copy.kbProductPlaceholder}
            </span>
          )}
          <ChevronDownIcon className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
        </summary>

        <div class="absolute left-0 right-0 z-20 mt-1 rounded-md border border-border bg-card p-2 shadow-lg">
          <div class="mb-1.5 flex items-center gap-1.5 rounded-md border border-input bg-background px-2 py-1.5 transition-colors duration-200 ease-expo focus-within:border-ring">
            <SearchIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <input
              type="search"
              value={query}
              placeholder={copy.kbProductSearch}
              onInput={(e) => setQuery((e.target as HTMLInputElement).value)}
              class="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            />
          </div>

          {/* overflow-x-hidden is not redundant: per spec, setting one axis to
            something other than `visible` makes the other compute to `auto`, so
            a y-scroller hands itself an x-scrollbar the moment any row is wider
            than the panel. Product names here are long ("DASH Admin SaaS
            (Assessment Hub — sisi Admin & Assessor)"), so that was guaranteed. */}
          <ul class="flex max-h-56 flex-col gap-0.5 overflow-y-auto overflow-x-hidden">
            {filtered.map((product) => {
              const selected = value?.id === product.id && !value.isNew;
              return (
                <li key={product.id}>
                  <button
                    type="button"
                    onClick={() => chooseExisting(product)}
                    class={clsx(
                      // min-w-0: a flex item defaults to min-width:auto and
                      // refuses to shrink below its content, which is what lets
                      // a long product name push the row past the panel.
                      'flex w-full min-w-0 cursor-pointer items-start justify-between gap-2 rounded-md px-2.5 py-1.5 text-left',
                      'transition-all duration-150 ease-expo hover:bg-accent/60',
                      'motion-safe:hover:translate-x-[2px] motion-safe:active:scale-[0.99]',
                      'focus-visible:bg-accent/60 focus-visible:outline-none',
                      selected && 'bg-primary/10',
                    )}
                  >
                    <span class="flex min-w-0 flex-col">
                      <span
                        class={clsx(
                          'truncate text-sm font-medium',
                          selected ? 'text-primary' : 'text-foreground',
                        )}
                      >
                        {product.name}
                      </span>
                      <span class="truncate font-mono text-[0.68rem] text-muted-foreground">
                        {product.id}
                        {typeof product.doc_count === 'number' &&
                          ` · ${copy.kbProductDocs(product.doc_count)}`}
                      </span>
                    </span>
                    {selected && <CheckIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />}
                  </button>
                </li>
              );
            })}

            {!filtered.length && !canCreate && (
              <li class="px-2.5 py-2 text-sm text-muted-foreground">
                {loading ? copy.kbProductLoading : copy.kbProductNoMatch}
              </li>
            )}
          </ul>

          {canCreate && (
            <>
              <div class="my-1.5 border-t border-border" />
              <button
                type="button"
                onClick={chooseNew}
                class="flex w-full min-w-0 cursor-pointer flex-col rounded-md px-2.5 py-1.5 text-left transition-colors hover:bg-accent/60 focus-visible:bg-accent/60 focus-visible:outline-none"
              >
                {/* break-words, not truncate: this row echoes back what the
                  person just typed, so clipping it hides the thing they are
                  being asked to confirm. */}
                <span class="break-words text-sm font-medium text-primary">
                  {copy.kbProductCreate(trimmedQuery)}
                </span>
                <span class="break-all font-mono text-[0.68rem] text-muted-foreground">
                  {slugifyProductId(trimmedQuery) || '—'}
                </span>
              </button>
            </>
          )}
        </div>
      </details>

      {/* The id is editable only while creating. Deriving it silently would
        hide the one field that determines whether the document is findable
        later — and it is the field the old free-text form got wrong. */}
      {value?.isNew && (
        <div class="mt-2 rounded-md border border-border bg-muted/40 p-2.5">
          <label class="mb-1 block text-xs font-medium" for="kb-new-product-id">
            {copy.kbProductNewIdLabel}
          </label>
          <input
            id="kb-new-product-id"
            value={value.id}
            onInput={(e) => onChange({ ...value, id: (e.target as HTMLInputElement).value.trim() })}
            class={clsx(
              'w-full rounded-md border bg-background px-2.5 py-1.5 font-mono text-sm outline-none focus:border-primary',
              idTaken || idMalformed ? 'border-destructive' : 'border-border',
            )}
          />
          {idMalformed ? (
            <p class="mt-1 text-xs text-destructive">{copy.kbProductNewIdInvalid}</p>
          ) : idTaken ? (
            <p class="mt-1 text-xs text-destructive">{copy.kbProductNewIdTaken}</p>
          ) : (
            <p class="mt-1 text-xs text-muted-foreground">{copy.kbProductNewIdHint}</p>
          )}
          <p class="mt-1.5 text-xs text-muted-foreground">{copy.kbProductNewNote}</p>
          <button
            type="button"
            onClick={() => onChange(null)}
            class="mt-2 text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            {copy.kbProductClear}
          </button>
        </div>
      )}
    </div>
  );
}

/** True when this choice is safe to submit. Exported so the form and the
 *  component cannot disagree about what "valid" means. */
export function isProductChoiceValid(choice: ProductChoice | null, products: Product[]): boolean {
  if (!choice) return false;
  if (!choice.isNew) return true;
  return PRODUCT_ID_PATTERN.test(choice.id) && !products.some((p) => p.id === choice.id);
}
