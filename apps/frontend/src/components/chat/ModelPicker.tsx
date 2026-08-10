/** Model picker + bring-your-own-key control, in the header.
 *
 *  Atomic-design role: molecule. Replaces the read-only model chip that used to
 *  sit in ChatHeader showing `/api/meta`.
 *
 *  WHY IT LOOKS LIKE THIS
 *  Two controls that belong together: which model, and the key that makes it
 *  reachable. Splitting them across the UI would leave a picker full of options
 *  the user cannot explain the absence of. So an unavailable entry stays visible
 *  and says which variable credentials it — refusing without telling you what to
 *  do is the failure mode this avoids.
 *
 *  THE KEY
 *  Lives in `localStorage`, is sent per request in `X-Model-Api-Key`, and is
 *  never persisted server-side (ADR 0010). The help text says so in the UI
 *  rather than only in a doc, because a field asking for a credential owes the
 *  reader that answer at the moment they are deciding whether to paste it.
 *
 *  `type="password"` so it does not sit in plain sight on a shared screen — this
 *  is a header control in an office, and shoulder-surfing is the realistic
 *  threat, not cryptography.
 *
 *  Native <details>/<summary>, same as EvidencePanel: collapsible with no state
 *  to manage, keyboard operable and screen-reader announced for free.
 */
import { useMemo, useState } from 'preact/hooks';
import clsx from 'clsx';
import type { ModelOption } from '@/lib/chat';
import type { Copy } from '@/lib/copy';
import { ChevronDownIcon, InfoIcon, SearchIcon } from './icons';

/** How many entries render before the search box is the only way through.
 *
 *  The catalogue is derived from LiteLLM's registry — a few hundred models once
 *  several providers are credentialed — so the list cannot simply be dumped.
 *  Showing the recommended handful plus a filter keeps the common case one click
 *  away while leaving everything else reachable. */
const VISIBLE_LIMIT = 8;

/** Small spinner for the catalogue re-fetch.
 *
 *  `motion-safe:` so it respects prefers-reduced-motion — a spinner is exactly
 *  the kind of thing that setting exists for. */
function Spinner() {
  return (
    <span
      role="status"
      aria-live="polite"
      class="h-3 w-3 shrink-0 rounded-full border border-muted-foreground/30 border-t-primary motion-safe:animate-spin"
    />
  );
}

type ModelPickerProps = {
  copy: Copy;
  models: ModelOption[];
  /** True while the catalogue is being re-fetched after a key change. */
  loading: boolean;
  /** True when the catalogue could not be loaded even after retries. */
  failed: boolean;
  onRetry: () => void;
  modelId: string;
  onModelChange: (id: string) => void;
  apiKey: string;
  onApiKeyChange: (key: string) => void;
  offlineMode: boolean;
  onOfflineModeChange: (on: boolean) => void;
};

export function ModelPicker({
  copy,
  models,
  loading,
  failed,
  onRetry,
  modelId,
  onModelChange,
  apiKey,
  onApiKeyChange,
  offlineMode,
  onOfflineModeChange,
}: ModelPickerProps) {
  const [query, setQuery] = useState('');

  // Matching on id as well as label: the id is what someone copies out of a
  // provider's docs, so "qwen3.5-flash" should find it even though the label
  // reads "Qwen3.5 Flash 02 23".
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return models.slice(0, VISIBLE_LIMIT);
    return models
      .filter((m) => m.id.toLowerCase().includes(q) || m.label.toLowerCase().includes(q))
      .slice(0, 40);
  }, [models, query]);

  // Deliberately NOT `if (!models.length) return null`. That was the bug: a
  // failed /api/models call left the list empty and the whole control silently
  // vanished from the header, which reads as "this feature does not exist"
  // rather than "this request failed". The picker now always renders; only its
  // contents change.
  const active = models.find((m) => m.id === modelId);
  const hidden = models.length - filtered.length;
  // Nothing the server can authenticate — the key field is the only useful
  // thing in the panel, so lead with it instead of a list of dead ends.
  const noneCredentialed = models.length > 0 && !models.some((m) => m.available);

  return (
    <details class="group relative">
      <summary
        class="flex cursor-pointer list-none items-center gap-1.5 rounded-full border border-hairline bg-card/70 px-2.5 py-1 text-[0.6875rem] shadow-panel transition-all duration-200 ease-expo hover:border-primary/40 hover:shadow-raised focus-visible:border-ring focus-visible:shadow-glow focus-visible:outline-none motion-safe:active:scale-[0.97]"
        aria-label={copy.modelPickerAria}
      >
        <span class="font-mono text-muted-foreground">
          {active?.label ?? modelId.split('/').pop() ?? copy.modelPickerLabel}
        </span>
        {/* Visible without opening the panel. The entire reason this moved out
            of an env var is that "am I talking to the model right now?" should
            be answerable at a glance. `anim-pop` so it arrives with the same
            motion as everything else rather than snapping in. */}
        {offlineMode && (
          <span class="anim-pop shrink-0 rounded-full border border-gold/40 bg-gold/10 px-1.5 py-[1px] text-[0.65rem] font-medium text-gold">
            {copy.offlineModeBadge}
          </span>
        )}
        <ChevronDownIcon className="h-3 w-3 shrink-0 text-muted-foreground transition-transform duration-200 group-open:rotate-180" />
      </summary>

      {/* right-0 so the panel opens inward from the header's right edge instead
          of overflowing the viewport on a narrow screen.
          `anim-pop` is the existing popover entrance (global.css) — the same one
          the scope listbox uses, so the two dropdowns in this header behave
          identically instead of each having their own idea of "opening". It is
          already gated behind prefers-reduced-motion. */}
      <div class="anim-pop absolute right-0 top-full z-50 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-lg border border-border bg-card p-3 shadow-lg">
        {/* Title row: the section label, and the mode switch that governs it.
            Inline rather than a block of its own — it is one boolean, and giving
            it a bordered card made it look like the main event when the model
            list is. It sits OUTSIDE the fieldset below, or it would disable
            itself the moment it was switched on. */}
        <div class="mb-1.5 flex items-center gap-2">
          <p class="text-[0.7rem] font-semibold uppercase tracking-wide text-muted-foreground">
            {copy.modelPickerLabel}
          </p>
          <label class="ml-auto flex cursor-pointer select-none items-center gap-1.5">
            {/* The real checkbox is still here, just visually hidden. `sr-only`
                rather than `hidden` or a div-with-onClick: it keeps the label
                association, space-to-toggle, focus order and screen-reader
                announcement that a hand-built switch has to reimplement badly.
                The visible track below is decoration driven by state. */}
            <input
              type="checkbox"
              checked={offlineMode}
              onChange={(e) => onOfflineModeChange((e.target as HTMLInputElement).checked)}
              class="peer sr-only"
            />
            <span
              class={clsx(
                'text-[0.7rem] transition-colors duration-200',
                offlineMode ? 'text-foreground' : 'text-muted-foreground',
              )}
            >
              {copy.offlineModeLabel}
            </span>
            {/* Track + knob. `peer-focus-visible` puts the focus ring here, since
                the input it belongs to is invisible — without it the control is
                keyboard-operable but gives no sign of where focus is. */}
            <span
              class={clsx(
                'relative h-[15px] w-[26px] shrink-0 rounded-full transition-colors duration-200 ease-expo',
                'peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-1 peer-focus-visible:ring-offset-card',
                offlineMode ? 'bg-primary' : 'bg-muted-foreground/30',
              )}
            >
              <span
                class={clsx(
                  'absolute left-[2px] top-[2px] h-[11px] w-[11px] rounded-full bg-card shadow-sm',
                  // ease-snap overshoots very slightly, which is what makes a
                  // switch feel mechanical rather than like a fading rectangle.
                  'motion-safe:transition-transform motion-safe:duration-200 motion-safe:ease-snap',
                  offlineMode && 'translate-x-[11px]',
                )}
              />
            </span>
            {/* The long explanation lives here. A native tooltip is not reachable
                by keyboard or touch — the same limitation CitationList records —
                so this only ever holds the *background*: why the mode exists and
                what it costs. What it is doing RIGHT NOW is the visible line
                below, which appears exactly when it starts mattering. */}
            <InfoIcon
              className="h-3 w-3 shrink-0 text-muted-foreground"
              title={copy.offlineModeHelp}
            />
          </label>
        </div>

        {/* Visible, not tooltip-only. This is the sentence that explains why the
            controls under it stopped responding, and hiding that behind a hover
            would leave a touch user with a dead panel and no reason given. */}
        {offlineMode && (
          <p class="anim-in mb-2 rounded-md bg-muted px-2.5 py-1.5 text-[0.68rem] leading-relaxed text-muted-foreground">
            {copy.offlineModeLocks}
          </p>
        )}

        {/* Disabling here is the OPPOSITE case to the model rows below, and the
            difference is the whole reason one is acceptable and the other was
            not. Those were disabled on a GUESS — the server could not see the
            user's key, so it blocked access they might genuinely have. This is
            disabled on a FACT: offline mode makes these controls have no effect,
            and saying so is more honest than letting someone tune settings that
            change nothing. One click reverses it. */}
        <fieldset
          disabled={offlineMode}
          class={clsx('transition-opacity duration-300 ease-expo', offlineMode && 'opacity-45')}
        >
          {failed && (
            <div class="mb-2 rounded-md border border-hairline bg-muted px-2.5 py-2">
              <p class="text-[0.72rem] leading-relaxed text-muted-foreground">
                {copy.modelLoadFailed}
              </p>
              <button
                type="button"
                onClick={onRetry}
                class="mt-1.5 rounded-md border border-border px-2 py-0.5 text-[0.7rem] font-medium transition-colors hover:bg-accent"
              >
                {copy.gateRetry}
              </button>
            </div>
          )}

          {noneCredentialed && (
            <p class="mb-2 rounded-md bg-muted px-2.5 py-2 text-[0.72rem] leading-relaxed text-muted-foreground">
              {copy.modelNoneCredentialed}
            </p>
          )}

          <div class="mb-1.5 flex items-center gap-1.5 rounded-md border border-input bg-background px-2 py-1 transition-colors duration-200 ease-expo focus-within:border-ring">
            <SearchIcon className="h-3 w-3 shrink-0 text-muted-foreground" />
            <input
              type="search"
              value={query}
              placeholder={copy.modelSearchPlaceholder}
              onInput={(e) => setQuery((e.target as HTMLInputElement).value)}
              class="min-w-0 flex-1 bg-transparent text-[0.72rem] text-foreground outline-none placeholder:text-muted-foreground"
            />
            {/* Spins while the catalogue is being re-fetched after a key change.
              Filtering itself is local and instant, so this never reports on
              typing in THIS field — only on the request the key field starts. */}
            {loading && <Spinner />}
          </div>

          <ul
            class={clsx(
              'mb-2 flex max-h-72 flex-col gap-0.5 overflow-y-auto transition-opacity duration-200',
              loading && 'opacity-50',
            )}
          >
            {filtered.map((model) => {
              const selected = model.id === modelId;
              return (
                <li key={model.id}>
                  <button
                    type="button"
                    onClick={() => onModelChange(model.id)}
                    // Never disabled on `available`, on purpose. (The enclosing
                    // fieldset does disable these in offline mode — that is a
                    // different question, answered at the top of this file.)
                    //
                    // `available` is what the SERVER can see: its own env vars,
                    // plus whether the caller sent a key. It cannot see a key the
                    // user has not pasted yet, a provider key set on a different
                    // deployment, or a proxy that credentials the request further
                    // downstream. Disabling on that basis means our incomplete
                    // picture blocks access the person may genuinely have.
                    //
                    // So the flag becomes information, not a gate: pick anything,
                    // and if the credential is missing the provider says so in an
                    // error the user can act on. The real access control is
                    // `models.is_allowed` on the backend, which is about what this
                    // agent can drive — not about whose key it is.
                    class={clsx(
                      'flex w-full cursor-pointer flex-col rounded-md px-2.5 py-1.5 text-left',
                      'transition-all duration-150 ease-expo hover:bg-accent/60',
                      // A whole row sliding would be noisy in a list this dense;
                      // 2px is enough to feel responsive under the cursor.
                      'motion-safe:hover:translate-x-[2px] motion-safe:active:scale-[0.99]',
                      'focus-visible:bg-accent/60 focus-visible:outline-none',
                      selected && 'bg-primary/10',
                      // Dimmed, not blocked: reads as "you will need a key for
                      // this" rather than "you may not have this". Lifts to full
                      // opacity on hover so it stops looking inert.
                      !model.available && 'opacity-70 hover:opacity-100',
                    )}
                  >
                    <span
                      class={clsx(
                        'text-[0.8rem] font-medium',
                        selected ? 'text-primary' : 'text-foreground',
                      )}
                    >
                      {model.label}
                    </span>
                    {/* Three states, three different things to say. `your-key`
                      is the one worth spelling out: the server cannot vouch for
                      it, so the note transfers that uncertainty to the person
                      who owns the key rather than implying a guarantee. */}
                    <span class="text-[0.68rem] leading-snug text-muted-foreground">
                      {model.source === 'server'
                        ? model.note
                        : model.source === 'your-key'
                          ? copy.modelUsesYourKey
                          : copy.modelUnavailable(model.env_key)}
                    </span>
                  </button>
                </li>
              );
            })}
            {!filtered.length && (
              // "No match" and "no list" are different problems and used to share
              // a message: with the catalogue unloaded the panel claimed the
              // search found nothing, which sends the reader hunting for a typo
              // in a search box that was never the issue.
              <li class="px-2.5 py-2 text-[0.72rem] text-muted-foreground">
                {models.length
                  ? copy.modelNoMatch
                  : loading
                    ? copy.gateLoading
                    : copy.modelListEmpty}
              </li>
            )}
          </ul>

          {/* Says how much is not on screen, so the list reads as truncated rather
            than as the whole catalogue. */}
          {hidden > 0 && (
            <p class="mb-2 px-2.5 text-[0.68rem] text-muted-foreground">
              {copy.modelMoreAvailable(hidden)}
            </p>
          )}

          <div class="border-t border-hairline pt-2.5">
            <label
              for="model-api-key"
              class="mb-1 block text-[0.7rem] font-semibold uppercase tracking-wide text-muted-foreground"
            >
              {copy.modelKeyLabel}
            </label>
            <div class="flex items-center gap-1.5">
              <input
                id="model-api-key"
                type="password"
                autocomplete="off"
                spellcheck={false}
                value={apiKey}
                placeholder={copy.modelKeyPlaceholder}
                onInput={(e) => onApiKeyChange((e.target as HTMLInputElement).value)}
                class="min-w-0 flex-1 rounded-md border border-input bg-background px-2 py-1 font-mono text-[0.72rem] text-foreground outline-none transition-colors duration-200 ease-expo placeholder:text-muted-foreground focus-visible:border-ring"
              />
              {apiKey && (
                <button
                  type="button"
                  onClick={() => onApiKeyChange('')}
                  class="shrink-0 rounded-md px-2 py-1 text-[0.68rem] text-destructive transition-colors hover:bg-destructive/10"
                >
                  {copy.modelKeyClear}
                </button>
              )}
            </div>
            <p class="mt-1.5 text-[0.68rem] leading-relaxed text-muted-foreground">
              {copy.modelKeyHelp}
            </p>
          </div>
        </fieldset>
      </div>
    </details>
  );
}
