/**
 * ProductScopePicker — the active-scope control in the header.
 *
 * Atomic-design role: molecule. The initial choice happens at the gate
 * (ProductScopeGate); this control's only job is showing the active scope and
 * letting the user change it mid-conversation without losing the transcript.
 *
 * WHY THIS IS NO LONGER A NATIVE <select>:
 * The previous version kept a real <select> stretched invisibly over a custom
 * pill. That fixed the *closed* state but not the open one — the dropdown a
 * native select opens is drawn by the OS, outside the page, and CSS cannot
 * reach it. No amount of styling on our side changes those hard corners,
 * system fonts and instant appearance. Getting a dropdown that matches the
 * rest of the chrome means owning the popup, which means a listbox.
 *
 * What that costs, and how it is paid:
 * a native select comes with keyboard support, focus management and a screen
 * reader contract for free. Rebuilding it means implementing the ARIA listbox
 * pattern properly rather than dropping a styled <div> in:
 *
 *   • trigger  — aria-haspopup="listbox" + aria-expanded, so assistive tech
 *                announces it as a collapsed listbox rather than a button.
 *   • popup    — role="listbox"; each row role="option" with aria-selected.
 *   • focus    — the listbox itself takes focus and tracks the active row via
 *                aria-activedescendant (rather than moving DOM focus per row),
 *                which is the pattern screen readers expect here.
 *   • keyboard — Arrow keys, Home/End, Enter/Space to choose, Escape to
 *                cancel; focus always returns to the trigger on close so the
 *                tab order never jumps.
 *   • pointer  — a pointerdown listener on the document closes on outside
 *                click without swallowing the click that opened it.
 *
 * Deliberately NOT a Radix Select: that would pull in a portal/popper/focus
 * -scope dependency chain we do not otherwise have, to render a list of four
 * items into a header that never scrolls.
 *
 * Renders nothing before the gate is passed — there is no scope to display yet.
 */
import { useEffect, useRef, useState } from 'preact/hooks';
import { cn } from '@/lib/utils';
import { TargetIcon, ChevronDownIcon, CheckIcon } from './icons';
import type { Copy } from '@/lib/copy';
import type { Product } from '@/lib/chat';

type ProductScopePickerProps = {
  copy: Copy;
  products: Product[];
  activeProductId: string | null;
  onSelect: (id: string | null) => void;
  visible: boolean;
  /** Layout hook — the header uses this to reflow the control onto its own
   *  row below 640px. Purely positional; never style the control itself here. */
  className?: string;
};

// Sentinel for "all products" — an option value has to be a string, so null
// needs a stand-in that cannot collide with a real product id.
const ALL = '__all__';
const LISTBOX_ID = 'scope-listbox';
const optionDomId = (value: string) => `scope-option-${value}`;

export function ProductScopePicker({
  copy,
  products,
  activeProductId,
  onSelect,
  visible,
  className,
}: ProductScopePickerProps) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const options = [
    ...products.map((p) => ({ value: p.id, label: p.name, hint: p.id })),
    { value: ALL, label: copy.productScopeAll, hint: '' },
  ];
  const selectedValue = activeProductId ?? ALL;
  const selectedIndex = Math.max(
    0,
    options.findIndex((o) => o.value === selectedValue),
  );
  const activeLabel = options[selectedIndex]?.label ?? copy.productScopeAll;

  // Close on outside pointerdown. pointerdown rather than click: a click
  // listener registered during the opening click would fire immediately on
  // that same event and close the panel before it ever painted.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);

  // Move focus into the listbox once it exists, and keep the active row in
  // view when the list is long enough to scroll.
  useEffect(() => {
    if (!open) return;
    listRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    // Index into children rather than querying by id: product ids come from
    // the backend and would need CSS.escape to be safe in a selector.
    const node = listRef.current?.children[activeIndex];
    node?.scrollIntoView({ block: 'nearest' });
  }, [open, activeIndex]);

  const openList = () => {
    setActiveIndex(selectedIndex);
    setOpen(true);
  };

  const closeList = ({ refocus = true }: { refocus?: boolean } = {}) => {
    setOpen(false);
    if (refocus) triggerRef.current?.focus();
  };

  const choose = (index: number) => {
    const option = options[index];
    if (!option) return;
    onSelect(option.value === ALL ? null : option.value);
    closeList();
  };

  const onTriggerKeyDown = (event: KeyboardEvent) => {
    if (
      event.key === 'ArrowDown' ||
      event.key === 'ArrowUp' ||
      event.key === 'Enter' ||
      event.key === ' '
    ) {
      event.preventDefault();
      openList();
    }
  };

  const onListKeyDown = (event: KeyboardEvent) => {
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        setActiveIndex((i) => (i + 1) % options.length);
        break;
      case 'ArrowUp':
        event.preventDefault();
        setActiveIndex((i) => (i - 1 + options.length) % options.length);
        break;
      case 'Home':
        event.preventDefault();
        setActiveIndex(0);
        break;
      case 'End':
        event.preventDefault();
        setActiveIndex(options.length - 1);
        break;
      case 'Enter':
      case ' ':
        event.preventDefault();
        choose(activeIndex);
        break;
      case 'Escape':
        event.preventDefault();
        closeList();
        break;
      case 'Tab':
        // Let focus leave naturally, but do not leave an orphaned panel open.
        closeList({ refocus: false });
        break;
    }
  };

  if (!visible) return null;

  return (
    <div ref={rootRef} class={cn('relative inline-flex min-w-0', className)}>
      <button
        ref={triggerRef}
        type="button"
        // The pill itself. Same token vocabulary as the rest of the header, so
        // the closed state and the open panel finally belong to one system.
        class="group inline-flex h-7 w-full min-w-0 cursor-pointer items-center gap-1.5 rounded-full border border-hairline bg-card/70 pl-2.5 pr-1.5 shadow-panel transition-all duration-200 ease-expo hover:border-primary/40 hover:bg-card focus-visible:border-ring focus-visible:shadow-glow focus-visible:outline-none"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? LISTBOX_ID : undefined}
        aria-label={`${copy.scopeChangeAria}: ${activeLabel}`}
        title={activeLabel}
        onClick={() => (open ? closeList({ refocus: false }) : openList())}
        onKeyDown={onTriggerKeyDown}
      >
        <TargetIcon className="h-3.5 w-3.5 shrink-0 text-primary" />
        <span class="min-w-0 flex-1 truncate text-left text-[0.75rem] text-foreground">
          {activeLabel}
        </span>
        <ChevronDownIcon
          className={cn(
            'h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-200 ease-expo group-hover:text-foreground',
            open && 'rotate-180',
          )}
        />
      </button>

      {open && (
        <ul
          ref={listRef}
          id={LISTBOX_ID}
          role="listbox"
          tabIndex={-1}
          aria-label={copy.scopeChangeAria}
          aria-activedescendant={optionDomId(options[activeIndex]?.value ?? '')}
          onKeyDown={onListKeyDown}
          // left-0 on mobile (the pill spans the header's second row), pinned
          // right and given a comfortable minimum from sm up.
          // overflow-x-hidden pairs with overflow-y-auto on purpose: per spec,
          // a non-`visible` value on one axis makes the other compute to
          // `auto`, so this list would hand itself a horizontal scrollbar the
          // moment a row outgrew it. The rows truncate today, so nothing
          // overflows — this keeps it that way.
          class="anim-pop absolute left-0 right-0 top-full z-50 mt-1.5 max-h-[min(60vh,20rem)] overflow-y-auto overflow-x-hidden rounded-xl border border-hairline bg-popover p-1 shadow-raised backdrop-blur-xl focus:outline-none sm:left-auto sm:min-w-[15rem]"
        >
          {options.map((option, index) => {
            const isSelected = option.value === selectedValue;
            const isActive = index === activeIndex;
            return (
              <li
                key={option.value}
                id={optionDomId(option.value)}
                role="option"
                aria-selected={isSelected}
                // onMouseMove, not onMouseEnter: with the keyboard driving the
                // active row, a stationary cursor that merely happens to sit
                // over the list would otherwise yank the highlight back on the
                // first re-render.
                onMouseMove={() => setActiveIndex(index)}
                onClick={() => choose(index)}
                class={cn(
                  'flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-[0.8125rem] transition-colors duration-150',
                  isActive ? 'bg-accent text-accent-foreground' : 'text-foreground',
                )}
              >
                <span class="flex min-w-0 flex-1 flex-col">
                  <span class="truncate leading-snug">{option.label}</span>
                  {option.hint && (
                    <span class="truncate font-mono text-[0.6875rem] text-muted-foreground">
                      {option.hint}
                    </span>
                  )}
                </span>
                {/* The tick is the only selection marker, so it keeps its slot
                    reserved — otherwise every row shifts by 14px as the
                    selection moves. */}
                <span class="w-3.5 shrink-0 text-primary" aria-hidden="true">
                  {isSelected && <CheckIcon className="h-3.5 w-3.5" />}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
