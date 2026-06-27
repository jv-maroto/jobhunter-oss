"use client";

import * as React from "react";
import { Moon, Sun, Monitor } from "lucide-react";
import { useTheme } from "next-themes";
import { motion, AnimatePresence } from "motion/react";
import { Button } from "@/components/ui/button";
import { PaletteSwitcher } from "./PaletteSwitcher";

/** Dark / light / system cycle + accent-palette picker, grouped together. */
export function ThemeToggle() {
  return (
    <div className="flex items-center gap-1">
      <PaletteSwitcher />
      <ModeToggle />
    </div>
  );
}

function ModeToggle() {
  const { theme, setTheme } = useTheme();
  const mounted = React.useSyncExternalStore(
    React.useCallback(() => () => {}, []),
    () => true,
    () => false,
  );

  if (!mounted) {
    return (
      <Button variant="ghost" size="icon" aria-label="Toggle theme">
        <Sun />
      </Button>
    );
  }

  const cycle = () => {
    if (theme === "dark") setTheme("light");
    else if (theme === "light") setTheme("system");
    else setTheme("dark");
  };

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Cycle theme"
      onClick={cycle}
      className="relative overflow-hidden"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={theme ?? "system"}
          initial={{ y: -16, opacity: 0, rotate: -45 }}
          animate={{ y: 0, opacity: 1, rotate: 0 }}
          exit={{ y: 16, opacity: 0, rotate: 45 }}
          transition={{ duration: 0.18 }}
          className="absolute inset-0 grid place-items-center"
        >
          {theme === "dark" ? (
            <Moon className="h-4 w-4 text-[hsl(var(--accent-1))]" />
          ) : theme === "light" ? (
            <Sun className="h-4 w-4 text-[hsl(var(--accent-2))]" />
          ) : (
            <Monitor className="h-4 w-4" />
          )}
        </motion.span>
      </AnimatePresence>
    </Button>
  );
}
