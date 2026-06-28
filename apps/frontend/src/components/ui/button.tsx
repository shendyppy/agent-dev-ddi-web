/**
 * Button — shadcn/ui button, ported to run on Preact via preact/compat.
 *
 * `import * as React from 'react'` resolves to preact/compat (aliased in
 * astro.config.mjs `preact({ compat: true })`), so forwardRef and the React
 * HTML attribute types work unchanged. `@radix-ui/react-slot` powers `asChild`
 * — render the button's styles onto a child element (e.g. an <a>) instead of a
 * <button>.
 *
 * Variants/sizes are cva-driven; pass `className` to override (tailwind-merge
 * dedupes conflicts so your override wins).
 */
import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

// Motion: every button gets a short `transition-all` (so colour AND transform
// animate together) plus a gentle `active:scale` press — the missing tactile
// feel that made the old `transition-colors`-only buttons read as flat. The
// press is wrapped in `motion-safe:` so users with prefers-reduced-motion get a
// fully static button. Filled variants (default/secondary/destructive) also
// lift ~2px on hover for a quiet "raise"; outline/ghost/link stay flat since
// their hover is already a fill/border change.
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all duration-200 ease-out cursor-pointer motion-safe:active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90 motion-safe:hover:-translate-y-0.5',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80 motion-safe:hover:-translate-y-0.5',
        outline: 'border border-input bg-background text-foreground hover:bg-muted',
        ghost: 'text-foreground hover:bg-muted',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90 motion-safe:hover:-translate-y-0.5',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 rounded-md px-3 text-xs',
        lg: 'h-10 rounded-md px-6',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
    );
  },
);
Button.displayName = 'Button';

export { Button, buttonVariants };
