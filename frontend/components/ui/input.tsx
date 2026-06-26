import * as React from "react";
import { cn } from "@/lib/utils";

const baseInputClass =
  "flex w-full rounded-md bg-white/[0.03] border border-[hsl(var(--border))] px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 transition-colors focus-visible:outline-none focus-visible:border-[hsl(var(--accent-1))]/60 focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-1))]/25 disabled:cursor-not-allowed disabled:opacity-50";

const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, type, ...props }, ref) => (
  <input
    type={type}
    ref={ref}
    className={cn(baseInputClass, "h-9", className)}
    {...props}
  />
));
Input.displayName = "Input";

const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(baseInputClass, "py-2.5 leading-relaxed resize-y", className)}
    {...props}
  />
));
Textarea.displayName = "Textarea";

export { Input, Textarea };
