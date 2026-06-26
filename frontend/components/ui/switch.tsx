"use client";

import * as React from "react";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";

const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitive.Root
    ref={ref}
    className={cn(
      "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border border-[hsl(var(--border-strong))] transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-1))]/40 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-[hsl(var(--accent-1))]/25 data-[state=checked]:border-[hsl(var(--accent-1))]/55 data-[state=checked]:shadow-[0_0_12px_-2px_hsl(var(--accent-1)/0.55)] data-[state=unchecked]:bg-white/[0.04]",
      className,
    )}
    {...props}
  >
    <SwitchPrimitive.Thumb
      className={cn(
        "pointer-events-none block h-3.5 w-3.5 rounded-full bg-foreground shadow ring-0 transition-transform data-[state=checked]:translate-x-4 data-[state=checked]:bg-[hsl(var(--accent-1))] data-[state=unchecked]:translate-x-0.5",
      )}
    />
  </SwitchPrimitive.Root>
));
Switch.displayName = SwitchPrimitive.Root.displayName;

export { Switch };
