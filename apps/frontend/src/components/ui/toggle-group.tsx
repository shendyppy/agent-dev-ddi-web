/**
 * ToggleGroup — shadcn/ui toggle group, ported to Preact via preact/compat.
 *
 * Wraps @radix-ui/react-toggle-group (roving focus + single/multi selection).
 * Used for the ID/EN language switch as a segmented control. The
 * `toggleVariants` cva is inlined here (rather than imported from a separate
 * toggle.tsx) so we don't need the standalone @radix-ui/react-toggle package.
 *
 * Visual model = a "pill" segmented control (iOS/Material 3 style): the Root is
 * a rounded-full track with inset padding, and each item is a rounded-full pill
 * that raises into a maroon "knob" (bg-primary + shadow-sm) when selected. This
 * replaced an older sharp-cornered (rounded-sm) secondary-fill version that read
 * as dated. The track owns the muted fill, so items only swap text colour on
 * hover (no double fill), and every item gets the same gentle active:scale press
 * as the ui/Button, gated behind prefers-reduced-motion via motion-safe:.
 */
import * as React from 'react';
import * as ToggleGroupPrimitive from '@radix-ui/react-toggle-group';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const toggleVariants = cva(
  'inline-flex items-center justify-center rounded-full text-xs font-medium transition-all duration-200 cursor-pointer text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset disabled:pointer-events-none disabled:opacity-50 motion-safe:active:scale-[0.95] data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:shadow-sm',
  {
    // h-7 rather than h-6: at 24px the pills were an awkward tap target on a
    // phone. 28px inside a 36px track is still compact enough for the header
    // while being meaningfully easier to hit.
    variants: { size: { default: 'h-7 px-3', sm: 'h-5 px-2' } },
    defaultVariants: { size: 'default' },
  },
);

type ToggleSize = VariantProps<typeof toggleVariants>['size'];

const ToggleGroupContext = React.createContext<{ size: ToggleSize }>({ size: 'default' });

// Radix types Root's props as a discriminated union keyed on `type`
// (ToggleGroupSingleProps | ToggleGroupMultipleProps). Once this wrapper
// rest-destructures className/size/children, the remaining object is no longer
// provably one arm of that union, so passing it back — together with a ref —
// fails to type-check even though every caller supplies a literal `type`.
// Flattening the discriminant for the internal hand-off keeps every other prop
// checked; the real union is still enforced on ToggleGroup's own props below,
// which is the boundary callers actually touch.
const ToggleGroupRoot = ToggleGroupPrimitive.Root as React.ComponentType<
  Omit<React.ComponentPropsWithoutRef<typeof ToggleGroupPrimitive.Root>, 'type'> & {
    type?: 'single' | 'multiple';
    ref?: React.Ref<HTMLDivElement>;
  }
>;

const ToggleGroup = React.forwardRef<
  React.ElementRef<typeof ToggleGroupPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ToggleGroupPrimitive.Root> &
    VariantProps<typeof toggleVariants>
>(({ className, size, children, ...props }, ref) => (
  <ToggleGroupRoot
    ref={ref}
    className={cn(
      'inline-flex items-center gap-1 rounded-full border border-hairline bg-card/70 p-1 shadow-panel',
      className,
    )}
    {...props}
  >
    <ToggleGroupContext.Provider value={{ size }}>{children}</ToggleGroupContext.Provider>
  </ToggleGroupRoot>
));
ToggleGroup.displayName = ToggleGroupPrimitive.Root.displayName;

const ToggleGroupItem = React.forwardRef<
  React.ElementRef<typeof ToggleGroupPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof ToggleGroupPrimitive.Item> &
    VariantProps<typeof toggleVariants>
>(({ className, children, size, ...props }, ref) => {
  const context = React.useContext(ToggleGroupContext);
  return (
    <ToggleGroupPrimitive.Item
      ref={ref}
      className={cn(toggleVariants({ size: size ?? context.size }), className)}
      {...props}
    >
      {children}
    </ToggleGroupPrimitive.Item>
  );
});
ToggleGroupItem.displayName = ToggleGroupPrimitive.Item.displayName;

export { ToggleGroup, ToggleGroupItem };
