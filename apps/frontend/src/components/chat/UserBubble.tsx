/** Right-aligned user message bubble (pale-maroon tint). */
export function UserBubble({ content }: { content: string }) {
  return (
    <div class="anim-in flex w-full justify-end">
      <div class="max-w-[72%] rounded-lg bg-primary-soft px-[18px] py-3 text-[0.9375rem] leading-relaxed text-foreground">
        {content}
      </div>
    </div>
  );
}
