/** Left-aligned assistant row: avatar gutter + content. Shared by message, tool
 *  chip, and typing indicator so they line up identically.
 *
 *  SYMMETRY — the shared gutter.
 *  The avatar pushes assistant content 42px in from the left (w-8 + gap-2.5),
 *  while user bubbles used to sit flush against the right edge. The column was
 *  therefore inset on one side and not the other, which is what read as "not
 *  symmetric". GUTTER (exported) is that measurement; UserBubble applies it as
 *  right padding, so both roles now breathe equally against the transcript
 *  edges. Change it here and both sides stay in step.
 *
 *  GROUPING — consecutive assistant rows (an answer, its tool chips, the typing
 *  indicator) keep the gutter but drop the repeated avatar. Restamping the same
 *  glyph every 40px turned a single reply into a visually stuttering stack.
 *
 *  RESPONSIVE: the row claims nearly the full column on a phone and only pulls
 *  back to 88% from sm up. min-w-0 on the content wrapper is what actually lets
 *  code blocks and tables shrink — without it a flex child refuses to go below
 *  its intrinsic width and the whole transcript scrolls sideways. */
import type { ComponentChildren } from 'preact';
import { AssistantAvatar } from './AssistantAvatar';

/** Avatar width + row gap. Mirrored as right padding on UserBubble. */
export const GUTTER = 'pr-[42px] sm:pr-[44px]';

export function AssistantRow({
  children,
  streaming = false,
  grouped = false,
}: {
  children: ComponentChildren;
  /** True only for the in-flight turn — drives the avatar's halo pulse. */
  streaming?: boolean;
  /** True when the previous row was also assistant-side; hides the avatar but
   *  preserves its footprint so content stays on the same vertical line. */
  grouped?: boolean;
}) {
  return (
    <div class="anim-in flex w-full justify-start">
      <div class="flex max-w-full gap-2.5 py-1 sm:max-w-[88%] sm:gap-3">
        {grouped ? (
          <div class="w-8 shrink-0" aria-hidden="true" />
        ) : (
          <AssistantAvatar streaming={streaming} />
        )}
        <div class="min-w-0 flex-1">{children}</div>
      </div>
    </div>
  );
}
