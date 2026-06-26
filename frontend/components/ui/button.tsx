"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "relative inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium select-none transition-all duration-200 ease-out focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        // Primary CTA — cyan glass with shimmer on hover
        default:
          "bg-[hsl(var(--accent-1))]/15 text-[hsl(var(--accent-1))] border border-[hsl(var(--accent-1))]/30 backdrop-blur-md shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] hover:bg-[hsl(var(--accent-1))]/22 hover:border-[hsl(var(--accent-1))]/55 hover:shadow-[0_0_24px_-4px_hsl(var(--accent-1)/0.55)]",
        // Solid CTA — high impact
        solid:
          "bg-[hsl(var(--accent-1))] text-[hsl(var(--primary-foreground))] border border-transparent hover:brightness-110 shadow-[0_8px_24px_-6px_hsl(var(--accent-1)/0.45)]",
        outline:
          "border border-[hsl(var(--border-strong))] bg-transparent text-foreground hover:bg-white/5 hover:border-[hsl(var(--accent-1))]/40",
        ghost:
          "text-muted-foreground hover:text-foreground hover:bg-white/5",
        glass:
          "glass glass-hover text-foreground",
        destructive:
          "bg-[hsl(var(--destructive))]/15 text-[hsl(var(--destructive))] border border-[hsl(var(--destructive))]/30 hover:bg-[hsl(var(--destructive))]/25",
        link: "text-[hsl(var(--accent-1))] underline-offset-4 hover:underline",
        warn:
          "bg-[hsl(var(--accent-warn))]/15 text-[hsl(var(--accent-warn))] border border-[hsl(var(--accent-warn))]/30 hover:bg-[hsl(var(--accent-warn))]/22",
      },
      size: {
        default: "h-9 px-4 [&_svg]:h-4 [&_svg]:w-4",
        sm: "h-8 px-3 text-xs [&_svg]:h-3.5 [&_svg]:w-3.5",
        lg: "h-11 px-6 text-base [&_svg]:h-4 [&_svg]:w-4",
        icon: "h-9 w-9 [&_svg]:h-4 [&_svg]:w-4",
        "icon-sm": "h-8 w-8 [&_svg]:h-3.5 [&_svg]:w-3.5",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  shimmer?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, shimmer, children, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(
          buttonVariants({ variant, size, className }),
          shimmer && "overflow-hidden",
        )}
        ref={ref}
        {...props}
      >
        {shimmer && (
          <span
            aria-hidden
            className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/15 to-transparent transition-transform duration-700 ease-out group-hover:translate-x-full"
          />
        )}
        {children}
      </Comp>
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
