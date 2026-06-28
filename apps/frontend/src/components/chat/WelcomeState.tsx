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
    <div class="anim-in mt-[10vh] flex flex-col gap-4">
      <div class="border-l-[3px] border-gold pl-3">
        <h2 class="m-0 text-[1.375rem] font-semibold leading-snug tracking-[-0.02em]">
          {copy.welcomeHeading}
        </h2>
      </div>

      <p class="m-0 max-w-[58ch] text-[0.9375rem] leading-relaxed text-muted-foreground">
        {copy.welcomeSubtitle}
      </p>

      <div class="mt-1 flex flex-wrap gap-2">
        {copy.suggestedPrompts.map((p, i) => (
          <Button
            key={p}
            type="button"
            variant="outline"
            // Outline chip, softened: muted label, auto height so the wrap
            // padding reads as a chip not a button. anim-in + a per-index delay
            // gives the chips a quick cascading entrance (gated by reduced-motion
            // in global.css, so the delay is harmless when motion is off).
            className="anim-in h-auto rounded-md px-3.5 py-2 text-left text-[0.875rem] font-normal text-muted-foreground hover:border-primary hover:text-foreground"
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
