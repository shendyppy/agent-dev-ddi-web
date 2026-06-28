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
      <span class="inline-flex items-center gap-1.5 rounded-xs border border-border px-2.5 py-[3px]">
        <Icon className="h-3 w-3 shrink-0" />
        {label}
      </span>
    </div>
  );
}
