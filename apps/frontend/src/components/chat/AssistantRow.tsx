/** Left-aligned assistant row: avatar + content. Shared by message, tool chip,
 *  and typing indicator so they line up identically. */
import type { ComponentChildren } from 'preact';
import { AssistantAvatar } from './AssistantAvatar';

export function AssistantRow({ children }: { children: ComponentChildren }) {
  return (
    <div class="anim-in flex w-full justify-start">
      <div class="flex max-w-[88%] gap-3 py-1">
        <AssistantAvatar />
        {children}
      </div>
    </div>
  );
}
