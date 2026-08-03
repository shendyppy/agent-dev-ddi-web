import type { Copy } from '@/lib/copy';
import type { ChatSession } from '@/hooks/use-history';

type HistoryPanelProps = {
  copy: Copy;
  open: boolean;
  onClose: () => void;
  sessions: ChatSession[];
  loading: boolean;
  activeSessionId: string | null;
  onSelectSession: (session: ChatSession) => void;
  onNewChat: () => void;
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function HistoryPanel({
  copy,
  open,
  onClose,
  sessions,
  loading,
  activeSessionId,
  onSelectSession,
  onNewChat,
}: HistoryPanelProps) {
  return (
    <>
      {/* Backdrop — always in DOM so opacity can animate */}
      <div
        aria-hidden="true"
        onClick={onClose}
        class={[
          'fixed inset-0 z-30 bg-black/30 backdrop-blur-sm transition-opacity duration-250 sm:hidden',
          open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none',
        ].join(' ')}
      />

      {/* Panel — always in DOM, slide via translate */}
      <aside
        aria-label={copy.historyLabel}
        class={[
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-border bg-card shadow-xl',
          'transition-transform duration-250 ease-in-out',
          open ? 'translate-x-0' : '-translate-x-full',
        ].join(' ')}
      >
        <div class="flex items-center justify-between border-b border-border px-4 py-3">
          <span class="text-sm font-semibold">{copy.historyLabel}</span>
          <button
            type="button"
            onClick={onClose}
            class="rounded p-1 text-muted-foreground hover:bg-muted transition-colors"
            aria-label="Tutup"
          >
            <svg class="h-4 w-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 3l10 10M13 3L3 13" stroke-linecap="round" />
            </svg>
          </button>
        </div>

        <div class="px-3 pt-3">
          <button
            type="button"
            onClick={onNewChat}
            class="flex w-full items-center gap-2 rounded-md border border-dashed border-border px-3 py-2 text-sm text-muted-foreground hover:border-primary hover:text-primary transition-colors"
          >
            <svg class="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M8 3v10M3 8h10" stroke-linecap="round" />
            </svg>
            {copy.historyNewChat}
          </button>
        </div>

        <div class="flex-1 overflow-y-auto px-3 py-2">
          {loading ? (
            <p class="px-1 py-3 text-xs text-muted-foreground">{copy.historyLoading}</p>
          ) : sessions.length === 0 ? (
            <p class="px-1 py-3 text-xs text-muted-foreground">{copy.historyEmpty}</p>
          ) : (
            <ul class="space-y-0.5">
              {sessions.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => onSelectSession(s)}
                    class={[
                      'flex w-full flex-col rounded-md px-3 py-2 text-left transition-colors',
                      s.id === activeSessionId
                        ? 'bg-primary/10 text-primary'
                        : 'hover:bg-muted text-foreground',
                    ].join(' ')}
                  >
                    <span class="truncate text-xs font-medium leading-snug">{s.title}</span>
                    <span class="mt-0.5 text-[0.625rem] text-muted-foreground">
                      {s.product_scope ?? copy.productScopeAll} · {formatDate(s.created_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </>
  );
}
