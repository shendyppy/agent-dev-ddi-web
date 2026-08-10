/**
 * ChatHeader — the top bar of the chat shell.
 *
 * Atomic-design role: organism. Composes four smaller pieces:
 *   • the brand mark (document glyph on a maroon tile) + app title
 *   • the ProductScopePicker (active retrieval scope, once the gate is passed)
 *   • the ModelPicker (which model answers, plus the user's own API key)
 *   • the LanguageToggle molecule (ID/EN segmented control)
 *
 * The scope picker lives here rather than above the composer because it is now
 * persistent conversation state, not a per-message option: the gate sets it and
 * the header is where you see and change it.
 *
 * Keeping the header isolated means Chat.tsx never needs to know what goes in
 * the bar — it just renders <ChatHeader … />. Every color references a token
 * from global.css @theme (bg-background, bg-primary, text-muted-foreground…),
 * never a raw hex.
 */
import { useState, useRef, useEffect } from 'preact/hooks';
import { LanguageToggle } from './LanguageToggle';
import { ProductScopePicker } from './ProductScopePicker';
import { ModelPicker } from './ModelPicker';
import { DocumentIcon } from './icons';
import { isSupabaseConfigured } from '@/lib/supabase';
import type { Copy, Language } from '@/lib/copy';
import type { ModelOption, Product } from '@/lib/chat';
import type { User } from '@supabase/supabase-js';

type ChatHeaderProps = {
  copy: Copy;
  lang: Language;
  onLangChange: (next: Language) => void;
  products: Product[];
  activeProductId: string | null;
  onScopeChange: (id: string | null) => void;
  scopeChosen: boolean;
  user: User | null;
  onLogin: () => void;
  onLogout: () => void;
  onHistoryToggle: () => void;
  models: ModelOption[];
  modelsLoading: boolean;
  modelsFailed: boolean;
  onRetryModels: () => void;
  modelId: string;
  onModelChange: (id: string) => void;
  apiKey: string;
  onApiKeyChange: (key: string) => void;
  offlineMode: boolean;
  onOfflineModeChange: (on: boolean) => void;
};

export function ChatHeader({
  copy,
  lang,
  onLangChange,
  products,
  activeProductId,
  onScopeChange,
  scopeChosen,
  user,
  onLogin,
  onLogout,
  onHistoryToggle,
  models,
  modelsLoading,
  modelsFailed,
  onRetryModels,
  modelId,
  onModelChange,
  apiKey,
  onApiKeyChange,
  offlineMode,
  onOfflineModeChange,
}: ChatHeaderProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!dropdownOpen) return;
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [dropdownOpen]);
  return (
    <>
      <header class="edge-fade sticky top-0 z-20 flex flex-wrap items-center gap-x-3 gap-y-2 bg-background/80 px-4 py-2.5 backdrop-blur-xl sm:flex-nowrap sm:justify-between sm:gap-4 sm:px-6 sm:py-3">
        <div class="flex min-w-0 flex-1 items-center gap-2.5">
          {/* Document glyph on a maroon tile — deliberately not a star/sparkle,
            which reads as a generic AI product. The sheen + ring turn the flat
            swatch into a lit surface. */}
          <span
            class="tile-sheen inline-flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-panel ring-1 ring-inset ring-white/15"
            aria-hidden="true"
          >
            <DocumentIcon className="h-4 w-4" />
          </span>
          <h1 class="m-0 truncate text-[0.9375rem] font-semibold tracking-[-0.01em]">
            {copy.appTitle}
          </h1>
          {user && (
            <button
              type="button"
              onClick={onHistoryToggle}
              aria-label={copy.historyAria}
              class="ml-1 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            >
              <svg
                class="h-4 w-4"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
              >
                <path d="M8 1.5A6.5 6.5 0 1 1 1.5 8" stroke-linecap="round" />
                <path d="M1.5 4V8H5.5" stroke-linecap="round" stroke-linejoin="round" />
                <path d="M8 4.5V8l2.5 1.5" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          )}
        </div>

        {/* order-last + basis-full: second row on mobile, inline from sm up. */}
        <ProductScopePicker
          copy={copy}
          products={products}
          activeProductId={activeProductId}
          onSelect={onScopeChange}
          visible={scopeChosen}
          className="order-last w-full basis-full sm:order-none sm:w-auto sm:basis-auto"
        />

        <div class="flex shrink-0 items-center gap-2.5">
          {/* Was a read-only chip echoing /api/meta. Now a real control: the
            model is a per-user choice, and the key that unlocks it belongs next
            to it. Hidden below md — on a phone the header has no room, and the
            stored choice still applies. */}
          <div class="hidden md:block">
            <ModelPicker
              copy={copy}
              models={models}
              loading={modelsLoading}
              failed={modelsFailed}
              onRetry={onRetryModels}
              modelId={modelId}
              onModelChange={onModelChange}
              apiKey={apiKey}
              onApiKeyChange={onApiKeyChange}
              offlineMode={offlineMode}
              onOfflineModeChange={onOfflineModeChange}
            />
          </div>
          <LanguageToggle lang={lang} onChange={onLangChange} copy={copy} />
          {user ? (
            <div class="relative" ref={dropdownRef}>
              <button
                type="button"
                onClick={() => setDropdownOpen((o) => !o)}
                aria-label={copy.logoutAria}
                aria-expanded={dropdownOpen}
                class="flex items-center gap-1.5 rounded-full ring-1 ring-border hover:ring-primary transition-all"
              >
                {user.user_metadata?.avatar_url ? (
                  <img
                    src={user.user_metadata.avatar_url as string}
                    alt={(user.user_metadata?.full_name as string) ?? user.email ?? ''}
                    class="h-7 w-7 rounded-full object-cover"
                    referrerpolicy="no-referrer"
                  />
                ) : (
                  <span class="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-[0.625rem] font-semibold text-primary-foreground">
                    {(user.email ?? '?')[0].toUpperCase()}
                  </span>
                )}
              </button>

              {dropdownOpen && (
                <div class="absolute right-0 top-full z-50 mt-2 w-52 rounded-lg border border-border bg-card shadow-lg">
                  <div class="border-b border-border px-3 py-2.5">
                    <p class="truncate text-xs font-medium">
                      {(user.user_metadata?.full_name as string) ?? ''}
                    </p>
                    <p class="truncate text-[0.6875rem] text-muted-foreground">{user.email}</p>
                  </div>
                  <div class="p-1">
                    <button
                      type="button"
                      onClick={() => {
                        setDropdownOpen(false);
                        setConfirmOpen(true);
                      }}
                      class="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10 transition-colors"
                    >
                      <svg
                        class="h-3.5 w-3.5"
                        viewBox="0 0 16 16"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.5"
                      >
                        <path
                          d="M6 2H3a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3M10 11l3-3-3-3M13 8H6"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        />
                      </svg>
                      {copy.logoutLabel}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            // Hidden when Supabase is not configured. Offering a sign-in button
            // that cannot sign anyone in is worse than not offering one: the
            // click does nothing and there is no way for the user to tell why.
            isSupabaseConfigured && (
              <button
                type="button"
                onClick={onLogin}
                class="rounded-md border border-border px-2.5 py-1 text-[0.75rem] font-medium text-foreground transition-colors hover:bg-accent"
              >
                {copy.loginWithGoogle}
              </button>
            )
          )}
        </div>
      </header>

      {confirmOpen && (
        <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div class="mx-4 w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-xl">
            <h2 class="mb-1 text-base font-semibold">{copy.logoutConfirmTitle}</h2>
            <p class="mb-5 text-sm text-muted-foreground">{copy.logoutConfirmBody}</p>
            <div class="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmOpen(false)}
                class="rounded-md border border-border px-4 py-1.5 text-sm font-medium hover:bg-muted transition-colors"
              >
                {copy.logoutConfirmCancel}
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirmOpen(false);
                  onLogout();
                }}
                class="rounded-md bg-destructive px-4 py-1.5 text-sm font-medium text-white hover:bg-destructive/90 transition-colors"
              >
                {copy.logoutConfirmYes}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
