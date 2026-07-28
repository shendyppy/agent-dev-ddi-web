/**
 * WelcomeState — the empty-conversation hero shown until the first message.
 *
 * Atomic-design role: molecule (composed of the ui/Button atom). The gold
 * left rule is the one brand flourish: it signals the product voice without
 * resorting to a coloured accent *word*, which is the #1 "generic AI chat"
 * visual tell. Suggested prompts seed the input on click (focus moves to the
 * composer) so the user never has to face a blank box. Each prompt chip fades
 * and rises in with a short stagger for a polished first impression.
 */
import { Button } from '@/components/ui/button';
import type { Copy } from '@/lib/copy';

type WelcomeStateProps = {
  copy: Copy;
  onPickPrompt: (prompt: string) => void;
};

export function WelcomeState({ copy, onPickPrompt }: WelcomeStateProps) {
  return (
    // mt scales down on short/phone viewports — a flat 10vh pushed the heading
    // near the fold on a landscape phone.
    <div class="anim-in mt-[6vh] flex flex-col gap-4 sm:mt-[10vh]">
      {/* The gold rule now fades out downward instead of stopping dead, so it
          reads as a light source rather than a border fragment. */}
      <div class="relative pl-3.5">
        <span
          class="absolute inset-y-0 left-0 w-[3px] rounded-full bg-gradient-to-b from-gold to-transparent"
          aria-hidden="true"
        />
        <h2 class="m-0 text-[1.25rem] font-semibold leading-snug tracking-[-0.02em] sm:text-[1.375rem]">
          {copy.welcomeHeading}
        </h2>
      </div>

      <p class="m-0 max-w-[58ch] text-[0.9375rem] leading-relaxed text-muted-foreground">
        {copy.welcomeSubtitle}
      </p>

      <div class="mt-1 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        {copy.suggestedPrompts.map((p, i) => (
          <Button
            key={p}
            type="button"
            variant="outline"
            // Outline chip, softened: muted label, auto height so the wrap
            // padding reads as a chip not a button. anim-in + a per-index delay
            // gives the chips a quick cascading entrance (gated by reduced-motion
            // in global.css, so the delay is harmless when motion is off).
            //
            // Stacked full-width below sm: wrapped chips at 360px produced a
            // ragged two-and-a-half-line block with one orphan, and each chip
            // fell under the 44px touch minimum.
            className="anim-in h-auto w-full justify-start whitespace-normal rounded-xl border-hairline bg-card/60 px-3.5 py-2.5 text-left text-[0.875rem] font-normal text-muted-foreground shadow-panel hover:border-primary/40 hover:bg-card hover:text-foreground hover:shadow-raised sm:w-auto"
            style={{ animationDelay: `${i * 70 + 120}ms` }}
            onClick={() => onPickPrompt(p)}
          >
            {p}
          </Button>
        ))}
      </div>
    </div>
  );
}
