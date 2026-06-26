import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider transition-colors",
  {
    variants: {
      variant: {
        default:
          "bg-[hsl(var(--accent-1))]/12 text-[hsl(var(--accent-1))] border border-[hsl(var(--accent-1))]/25",
        solid:
          "bg-[hsl(var(--accent-1))] text-[hsl(var(--primary-foreground))] border border-transparent",
        secondary:
          "bg-white/5 text-foreground border border-[hsl(var(--border))]",
        outline:
          "bg-transparent text-muted-foreground border border-[hsl(var(--border-strong))]",
        urgent:
          "bg-[hsl(var(--accent-warn))]/14 text-[hsl(var(--accent-warn))] border border-[hsl(var(--accent-warn))]/30",
        success:
          "bg-[hsl(var(--score-good))]/14 text-[hsl(var(--score-good))] border border-[hsl(var(--score-good))]/30",
        warn:
          "bg-[hsl(var(--score-mid))]/14 text-[hsl(var(--score-mid))] border border-[hsl(var(--score-mid))]/30",
        destructive:
          "bg-[hsl(var(--destructive))]/14 text-[hsl(var(--destructive))] border border-[hsl(var(--destructive))]/30",
        mono:
          "bg-white/4 text-muted-foreground border border-[hsl(var(--border))] font-mono normal-case tracking-normal",
      },
      size: {
        default: "h-5 text-[10px]",
        sm: "h-4 text-[9px] px-1.5",
        lg: "h-6 text-[11px] px-2.5",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, size, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant, size }), className)} {...props} />;
}

export { Badge, badgeVariants };
