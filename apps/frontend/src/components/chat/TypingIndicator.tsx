/** Quiet opacity-pulse typing indicator (the `typing-dot` keyframe lives in
 *  global.css; the literal class is kept so the static scanner leaves it). */
export function TypingIndicator({ label }: { label: string }) {
  return (
    <div class="flex items-center gap-2 py-1 text-[0.8125rem] text-muted-foreground">
      <span class="inline-flex items-center gap-1">
        <span class="typing-dot h-[5px] w-[5px] rounded-full bg-muted-foreground" />
        <span class="typing-dot h-[5px] w-[5px] rounded-full bg-muted-foreground" />
        <span class="typing-dot h-[5px] w-[5px] rounded-full bg-muted-foreground" />
      </span>
      <span>{label}</span>
    </div>
  );
}
