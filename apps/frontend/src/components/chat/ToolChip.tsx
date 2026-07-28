/** A small system-metadata chip shown while a tool runs ('calling') and after
 *  it returns ('result', dimmed). We never show raw tool args — those live in
 *  Langfuse traces; the user just sees a "working" affordance. */
import clsx from 'clsx';
import { SearchIcon, CheckIcon } from './icons';

export function ToolChip({ kind, label }: { kind: 'calling' | 'result'; label: string }) {
  const Icon = kind === 'calling' ? SearchIcon : CheckIcon;
  return (
    <div
      class={clsx(
        'flex flex-wrap items-center gap-2 font-mono text-[0.75rem] text-muted-foreground',
        kind === 'result' && 'opacity-60',
      )}
    >
      {/* rounded-full + card fill turns this from a boxy outline into a status
          pill, which is what it actually is. The 'calling' variant borrows the
          brand tint so an in-progress tool reads as active, not as metadata. */}
      <span
        class={clsx(
          'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-[3px] transition-colors duration-200',
          kind === 'calling'
            ? 'border-primary/25 bg-primary/5 text-primary'
            : 'border-hairline bg-card',
        )}
      >
        <Icon className="h-3 w-3 shrink-0" />
        {label}
      </span>
    </div>
  );
}
