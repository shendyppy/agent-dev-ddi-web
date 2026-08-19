/**
 * Submit a document to the knowledge base.
 *
 * Replaces an Ant Design modal wrapping one empty <textarea>. Three things
 * changed, and each one was a real failure rather than a style preference:
 *
 * 1. **Built on the app's own tokens.** antd shipped its own reset, its own
 *    blue, and hardcoded hexes into a UI that is otherwise shadcn + Tailwind,
 *    and it rode on the `react` → `@preact/compat` alias. It also landed in the
 *    main chat bundle for every visitor, most of whom never open this form.
 *
 * 2. **A document type that prefills headings.** A blank textarea asks a QA
 *    engineer to be a technical writer. Retrieval chunks on h1/h2/h3, so a
 *    document with no headings becomes one undifferentiated blob — and with an
 *    English embedder over an Indonesian corpus, structure is most of what
 *    retrieval has to work with. The outline is the feature.
 *
 * 3. **A product picker instead of two free-text fields.** `product_id` was
 *    typed by hand, which is how the corpus ended up with "klob mobile" and
 *    "learning hub mobile". Choosing from GET /api/products makes the id
 *    unforgeable and fills in the display name for free.
 *
 * Drafts are kept in localStorage: the previous version wiped every field on
 * close, so one stray Esc destroyed a half-hour of writing.
 */

import { useEffect, useMemo, useRef, useState } from 'preact/hooks';
import type { Product } from '@/lib/chat';
import type { Copy } from '@/lib/copy';

export type DocType = 'product' | 'feature' | 'runbook';

/**
 * Headings prefilled per document type, matching what PRODUCT-DOC-FORMAT.md
 * expects for that shape. Kept here rather than server-side so the writer sees
 * the structure while writing, which is the only moment it can influence them.
 */
const OUTLINES: Record<DocType, string[]> = {
  product: ['Overview', 'Cara menjalankan', 'Fitur', 'Environment', 'Masalah umum'],
  feature: ['Fungsinya apa', 'Cara mengaksesnya', 'Hak akses', 'Kasus khusus'],
  runbook: ['Health check', 'Gejala umum', 'Cara memperbaiki', 'Eskalasi ke siapa'],
};

const DRAFT_KEY = 'docagent.kbDraft';

/** Mirrors the server's `_safe_doc_name`, so the preview is not a guess. */
export function previewSlug(title: string): string {
  const stem = title.toLowerCase().endsWith('.md') ? title.slice(0, -3) : title;
  const safe = stem
    .replace(/[^a-zA-Z0-9_-]/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase();
  return `${safe || 'untitled'}.md`;
}

function outlineFor(docType: DocType): string {
  return OUTLINES[docType].map((heading) => `## ${heading}\n\n`).join('');
}

type Draft = {
  docType: DocType;
  title: string;
  productId: string;
  body: string;
};

type KnowledgeBaseModalProps = {
  copy: Copy;
  open: boolean;
  saving: boolean;
  products: Product[];
  productsLoading: boolean;
  error: string | null;
  onSubmit: (draft: Draft & { productName: string }) => void;
  onClose: () => void;
};

export function KnowledgeBaseModal({
  copy,
  open,
  saving,
  products,
  productsLoading,
  error,
  onSubmit,
  onClose,
}: KnowledgeBaseModalProps) {
  const [docType, setDocType] = useState<DocType>('feature');
  const [title, setTitle] = useState('');
  const [productId, setProductId] = useState('');
  const [body, setBody] = useState('');
  // Only shown after a submit attempt: flagging empty fields while someone is
  // still filling the form in is nagging, not help.
  const [attempted, setAttempted] = useState(false);
  const [draftRestored, setDraftRestored] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);

  // Restore a draft on open, or seed the body with the outline for the default
  // document type.
  useEffect(() => {
    if (!open) return;
    setAttempted(false);
    const stored = window.localStorage.getItem(DRAFT_KEY);
    if (stored) {
      try {
        const draft = JSON.parse(stored) as Draft;
        setDocType(draft.docType ?? 'feature');
        setTitle(draft.title ?? '');
        setProductId(draft.productId ?? '');
        setBody(draft.body ?? '');
        setDraftRestored(Boolean(draft.title || draft.body));
        return;
      } catch {
        // A corrupt draft is not worth a message; fall through to a fresh form.
      }
    }
    setDraftRestored(false);
    setBody(outlineFor('feature'));
    titleRef.current?.focus();
  }, [open]);

  // Persist on every change. Cheap, and it means a closed tab is recoverable.
  useEffect(() => {
    if (!open) return;
    const draft: Draft = { docType, title, productId, body };
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  }, [open, docType, title, productId, body]);

  // Esc closes, matching every other dialog in the app.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const selected = useMemo(() => products.find((p) => p.id === productId), [products, productId]);

  // Mirrors the server's validator, so the user finds out here rather than
  // through a rejected request.
  const missingTitle = !title.trim();
  const missingProduct = !productId;
  const missingBody = !body.trim();
  const missingHeading = !missingBody && !/^#{1,3} \S/m.test(body);
  const invalid = missingTitle || missingProduct || missingBody || missingHeading;

  function handleSwitchType(next: DocType) {
    setDocType(next);
    // Only replace the body when it is still an untouched outline — never
    // overwrite something the user has actually written. Checked against every
    // outline, not just the current type's, so switching twice in a row still
    // swaps cleanly.
    const untouched =
      !body.trim() || (Object.keys(OUTLINES) as DocType[]).some((t) => body === outlineFor(t));
    if (untouched) setBody(outlineFor(next));
  }

  function handleSubmit() {
    setAttempted(true);
    if (invalid || saving) return;
    onSubmit({
      docType,
      title: title.trim(),
      productId,
      productName: selected?.name ?? productId,
      body,
    });
  }

  if (!open) return null;

  return (
    <div
      class="fixed inset-0 z-50 flex items-end justify-center bg-black/40 backdrop-blur-sm sm:items-center"
      onClick={(e) => {
        if (e.target === e.currentTarget && !saving) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={copy.kbTitle}
        class="flex max-h-[92dvh] w-full max-w-2xl flex-col overflow-hidden rounded-t-xl border border-border bg-card shadow-xl sm:mx-4 sm:rounded-xl"
      >
        <header class="border-b border-border px-5 py-4">
          <h2 class="text-base font-semibold">{copy.kbTitle}</h2>
          <p class="mt-0.5 text-sm text-muted-foreground">{copy.kbSubtitle}</p>
        </header>

        <div class="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {draftRestored && (
            <p class="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
              {copy.kbDraftRestored}
            </p>
          )}

          <fieldset>
            <legend class="mb-1.5 text-sm font-medium">{copy.kbDocType}</legend>
            <div class="flex flex-wrap gap-2">
              {(
                [
                  ['feature', copy.kbDocTypeFeature],
                  ['product', copy.kbDocTypeProduct],
                  ['runbook', copy.kbDocTypeRunbook],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => handleSwitchType(value)}
                  aria-pressed={docType === value}
                  class={`rounded-full border px-3 py-1 text-sm transition-colors ${
                    docType === value
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <p class="mt-1.5 text-xs text-muted-foreground">{copy.kbDocTypeHint}</p>
          </fieldset>

          <div class="grid gap-4 sm:grid-cols-2">
            <div>
              <label class="mb-1.5 block text-sm font-medium" for="kb-title">
                {copy.kbTitleField}
              </label>
              <input
                id="kb-title"
                ref={titleRef}
                value={title}
                placeholder={copy.kbTitlePlaceholder}
                onInput={(e) => setTitle((e.target as HTMLInputElement).value)}
                class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
              {title.trim() ? (
                <p class="mt-1 text-xs text-muted-foreground">
                  {copy.kbSlugPreview(previewSlug(title))}
                </p>
              ) : (
                attempted &&
                missingTitle && <p class="mt-1 text-xs text-destructive">{copy.kbRequired}</p>
              )}
            </div>

            <div>
              <label class="mb-1.5 block text-sm font-medium" for="kb-product">
                {copy.kbProduct}
              </label>
              <select
                id="kb-product"
                value={productId}
                disabled={productsLoading}
                onChange={(e) => setProductId((e.target as HTMLSelectElement).value)}
                class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary disabled:opacity-60"
              >
                <option value="">
                  {productsLoading ? copy.kbProductLoading : copy.kbProductPlaceholder}
                </option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name}
                  </option>
                ))}
              </select>
              {attempted && missingProduct && (
                <p class="mt-1 text-xs text-destructive">{copy.kbRequired}</p>
              )}
            </div>
          </div>

          <div>
            <label class="mb-1.5 block text-sm font-medium" for="kb-body">
              {copy.kbContent}
            </label>
            <textarea
              id="kb-body"
              value={body}
              placeholder={copy.kbContentPlaceholder}
              onInput={(e) => setBody((e.target as HTMLTextAreaElement).value)}
              rows={12}
              class="w-full resize-y rounded-md border border-border bg-background px-3 py-2 font-mono text-sm leading-relaxed outline-none focus:border-primary"
            />
            {attempted && missingBody && (
              <p class="mt-1 text-xs text-destructive">{copy.kbRequired}</p>
            )}
            {attempted && missingHeading && (
              <p class="mt-1 text-xs text-destructive">{copy.kbNeedsHeading}</p>
            )}
          </div>

          {error && (
            <div class="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2">
              <p class="text-sm font-medium text-destructive">{copy.kbErrorTitle}</p>
              <p class="mt-0.5 text-xs text-destructive/90">{error}</p>
            </div>
          )}
        </div>

        <footer class="flex justify-end gap-2 border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            class="rounded-md border border-border px-4 py-1.5 text-sm font-medium transition-colors hover:bg-muted disabled:opacity-50"
          >
            {copy.kbCancel}
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving}
            class="rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {saving ? copy.kbSubmitting : copy.kbSubmit}
          </button>
        </footer>
      </div>
    </div>
  );
}

export { DRAFT_KEY, OUTLINES, outlineFor };
