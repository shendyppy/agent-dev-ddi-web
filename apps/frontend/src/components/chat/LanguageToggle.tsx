/** ID/EN language switch as a proper segmented control (Radix ToggleGroup). */
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import type { Copy, Language } from '@/lib/copy';

export function LanguageToggle({
  lang,
  onChange,
  copy,
}: {
  lang: Language;
  onChange: (next: Language) => void;
  copy: Copy;
}) {
  return (
    <ToggleGroup
      type="single"
      value={lang}
      // Radix emits '' when the active item is toggled off — ignore that so a
      // language is always selected.
      onValueChange={(value: string) => {
        if (value) onChange(value as Language);
      }}
      aria-label={copy.langToggleAria}
    >
      <ToggleGroupItem value="id" aria-label="Bahasa Indonesia">
        ID
      </ToggleGroupItem>
      <ToggleGroupItem value="en" aria-label="English">
        EN
      </ToggleGroupItem>
    </ToggleGroup>
  );
}
