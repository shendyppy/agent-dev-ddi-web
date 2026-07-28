/** Quiet opacity-pulse typing indicator (the `typing-dot` keyframe lives in
 *  global.css; the literal class is kept so the static scanner leaves it). */
export function TypingIndicator({ label }: { label: string }) {
  return (
    // The dots take the brand tint while a turn is live — paired with the
    // avatar halo it is the only place in the transcript that moves, so the
    // "working" state is unmistakable without a spinner.
    <div class="flex items-center gap-2 py-1.5 text-[0.8125rem] text-muted-foreground">
      <span class="inline-flex items-center gap-1">
        <span class="typing-dot h-[5px] w-[5px] rounded-full bg-primary" />
        <span class="typing-dot h-[5px] w-[5px] rounded-full bg-primary" />
        <span class="typing-dot h-[5px] w-[5px] rounded-full bg-primary" />
      </span>
      <span>{label}</span>
    </div>
  );
}
