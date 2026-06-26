import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const cardVariants = cva(
  "relative rounded-[var(--radius)] text-card-foreground",
  {
    variants: {
      variant: {
        glass: "glass",
        solid:
          "bg-[hsl(var(--surface))] border border-[hsl(var(--border))] shadow-[0_8px_30px_-12px_rgba(0,0,0,0.45)]",
        outline: "bg-transparent border border-[hsl(var(--border-strong))]",
        ghost: "bg-transparent",
      },
      tone: {
        none: "",
        accent:
          "before:absolute before:inset-0 before:rounded-[inherit] before:border before:border-[hsl(var(--accent-1))]/20 before:pointer-events-none",
        warn:
          "before:absolute before:inset-0 before:rounded-[inherit] before:border before:border-[hsl(var(--accent-warn))]/30 before:pointer-events-none",
      },
      hover: {
        none: "",
        lift: "glass-hover",
      },
    },
    defaultVariants: { variant: "glass", tone: "none", hover: "none" },
  },
);

export interface CardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {}

const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant, tone, hover, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(cardVariants({ variant, tone, hover }), className)}
      {...props}
    />
  ),
);
Card.displayName = "Card";

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("flex flex-col gap-1 px-5 pt-5 pb-3", className)}
      {...props}
    />
  ),
);
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "text-[15px] font-semibold leading-none tracking-tight font-[family-name:var(--font-display)]",
        className,
      )}
      {...props}
    />
  ),
);
CardTitle.displayName = "CardTitle";

const CardDescription = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("text-xs text-muted-foreground", className)} {...props} />
  ),
);
CardDescription.displayName = "CardDescription";

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("px-5 pb-5", className)} {...props} />
  ),
);
CardContent.displayName = "CardContent";

const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("flex items-center px-5 pb-5", className)}
      {...props}
    />
  ),
);
CardFooter.displayName = "CardFooter";

export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter, cardVariants };
