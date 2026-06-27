"use client";

import * as React from "react";
import { Palette, Check } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Selectable accent palettes. Each entry mirrors a `data-palette` block in
 * globals.css. The `swatch` colors are the dark-mode accent-1/accent-2 used
 * only to render the preview chip (the real theming happens via the CSS var
 * blocks keyed off the `id`).
 */
export const PALETTES = [
  { id: "cyan", label: "Cyan", from: "hsl(187 92% 49%)", to: "hsl(75 85% 60%)" },
  { id: "violet", label: "Violet", from: "hsl(262 83% 64%)", to: "hsl(322 84% 64%)" },
  { id: "emerald", label: "Emerald", from: "hsl(160 84% 45%)", to: "hsl(174 66% 56%)" },
  { id: "amber", label: "Amber", from: "hsl(38 95% 55%)", to: "hsl(20 90% 58%)" },
  { id: "rose", label: "Rose", from: "hsl(346 84% 61%)", to: "hsl(290 75% 65%)" },
] as const;

export type PaletteId = (typeof PALETTES)[number]["id"];

export const PALETTE_STORAGE_KEY = "jh_palette";
const DEFAULT_PALETTE: PaletteId = "cyan";

function isValid(value: string | null): value is PaletteId {
  return !!value && PALETTES.some((p) => p.id === value);
}

/** Read the persisted palette, falling back to the default. */
export function readStoredPalette(): PaletteId {
  if (typeof window === "undefined") return DEFAULT_PALETTE;
  try {
    const v = window.localStorage.getItem(PALETTE_STORAGE_KEY);
    return isValid(v) ? v : DEFAULT_PALETTE;
  } catch {
    return DEFAULT_PALETTE;
  }
}

/** Apply a palette to <html> and persist it. */
export function applyPalette(id: PaletteId) {
  if (typeof document !== "undefined") {
    document.documentElement.dataset.palette = id;
  }
  try {
    window.localStorage.setItem(PALETTE_STORAGE_KEY, id);
  } catch {
    /* ignore quota / privacy-mode errors */
  }
}

export function PaletteSwitcher() {
  const [open, setOpen] = React.useState(false);
  const [active, setActive] = React.useState<PaletteId>(DEFAULT_PALETTE);
  const [mounted, setMounted] = React.useState(false);
  const rootRef = React.useRef<HTMLDivElement>(null);

  // Restore the saved palette on mount.
  React.useEffect(() => {
    const stored = readStoredPalette();
    setActive(stored);
    if (typeof document !== "undefined") {
      document.documentElement.dataset.palette = stored;
    }
    setMounted(true);
  }, []);

  // Close on outside click / Escape.
  React.useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const choose = (id: PaletteId) => {
    setActive(id);
    applyPalette(id);
    setOpen(false);
  };

  if (!mounted) {
    return (
      <Button variant="ghost" size="icon" aria-label="Change accent palette">
        <Palette />
      </Button>
    );
  }

  return (
    <div ref={rootRef} className="relative">
      <Button
        variant="ghost"
        size="icon"
        aria-label="Change accent palette"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="relative"
      >
        <Palette className="h-4 w-4 text-[hsl(var(--accent-1))]" />
      </Button>

      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            initial={{ opacity: 0, y: -6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.96 }}
            transition={{ duration: 0.16, ease: [0.2, 0.7, 0.2, 1] }}
            className="glass-strong absolute right-0 top-[calc(100%+0.5rem)] z-50 w-52 p-2"
          >
            <p className="px-2 pb-1.5 pt-1 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
              Accent palette
            </p>
            <ul className="flex flex-col gap-0.5">
              {PALETTES.map((p) => {
                const isActive = p.id === active;
                return (
                  <li key={p.id}>
                    <button
                      type="button"
                      role="menuitemradio"
                      aria-checked={isActive}
                      onClick={() => choose(p.id)}
                      className={cn(
                        "group flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors",
                        isActive
                          ? "bg-[hsl(var(--accent-1))]/12 text-foreground"
                          : "text-muted-foreground hover:bg-white/5 hover:text-foreground",
                      )}
                    >
                      <span
                        aria-hidden
                        className={cn(
                          "h-5 w-5 shrink-0 rounded-full ring-1 ring-white/15",
                          isActive && "ring-2 ring-[hsl(var(--accent-1))]/70",
                        )}
                        style={{
                          backgroundImage: `linear-gradient(120deg, ${p.from}, ${p.to})`,
                        }}
                      />
                      <span className="flex-1 text-left">{p.label}</span>
                      {isActive && (
                        <Check className="h-3.5 w-3.5 text-[hsl(var(--accent-1))]" />
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
