/** Error bubble with a retry affordance. `content` is the already-friendly
 *  message (mapped through mapErrorToFriendly); `errorPrefix` frames it. */
import { Button } from '@/components/ui/button';
import type { Copy } from '@/lib/copy';

export function ErrorBubble({
  content,
  copy,
  onRetry,
}: {
  content: string;
  copy: Copy;
  onRetry: () => void;
}) {
  return (
    <div
      class="flex flex-col gap-2 rounded-xl border border-hairline border-l-[3px] border-l-destructive bg-card p-4 text-[0.9375rem] text-foreground shadow-panel"
      role="alert"
    >
      <p class="m-0">{copy.errorPrefix}</p>
      <p class="m-0 text-[0.8125rem] text-muted-foreground">{content}</p>
      {copy.errorHint && <p class="m-0 text-[0.8125rem] text-muted-foreground">{copy.errorHint}</p>}
      <Button type="button" variant="outline" size="sm" className="self-start" onClick={onRetry}>
        {copy.errorRetry}
      </Button>
    </div>
  );
}
