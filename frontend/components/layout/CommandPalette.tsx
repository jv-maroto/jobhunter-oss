"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { motion, AnimatePresence } from "motion/react";
import {
  Sparkles,
  KanbanSquare,
  BarChart3,
  Building2,
  ContactRound,
  Settings,
  RefreshCcw,
  Megaphone,
  Search,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

/** Minimal pub/sub so any component can open the palette */
type Listener = (open: boolean) => void;
const listeners = new Set<Listener>();
export const commandPaletteStore = {
  open: () => listeners.forEach((l) => l(true)),
  close: () => listeners.forEach((l) => l(false)),
};

interface NavCmd {
  id: string;
  label: string;
  hint: string;
  icon: typeof Sparkles;
  action: () => void;
}

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    listeners.add(setOpen);
    return () => {
      listeners.delete(setOpen);
    };
  }, []);

  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  const go = (path: string) => () => {
    setOpen(false);
    router.push(path);
  };

  const triggerScrape = async () => {
    setOpen(false);
    try {
      // Antes apuntaba a /scrape/trigger, que NO existe: daba 404 siempre y el
      // catch lo disfrazaba de "Backend offline".
      await api("/jobs/scrape-now", { method: "POST" });
      toast.success("Scrape lanzado", {
        description: "Corre en segundo plano; las ofertas iran apareciendo.",
      });
    } catch (e) {
      toast.error("No se pudo lanzar el scrape", {
        description: String(e).slice(0, 120),
      });
    }
  };

  const generateWeek = async () => {
    setOpen(false);
    try {
      await api("/posts/generate-week", { method: "POST" });
      toast.success("Week of posts generated");
    } catch {
      toast.error("Backend offline");
    }
  };

  const nav: NavCmd[] = [
    { id: "today", label: "Today", hint: "Fresh jobs + outreach", icon: Sparkles, action: go("/today") },
    { id: "pipeline", label: "Pipeline", hint: "Kanban of applications", icon: KanbanSquare, action: go("/pipeline") },
    { id: "metrics", label: "Metrics", hint: "Activity + API cost", icon: BarChart3, action: go("/metrics") },
    { id: "companies", label: "Companies", hint: "By employer", icon: Building2, action: go("/companies") },
    { id: "linkedin", label: "LinkedIn", hint: "Posts + connections", icon: ContactRound, action: go("/linkedin") },
    { id: "settings", label: "Settings", hint: "CV + appearance", icon: Settings, action: go("/settings") },
  ];

  const actions: NavCmd[] = [
    { id: "scrape", label: "Trigger scrape now", hint: "POST /jobs/scrape-now", icon: RefreshCcw, action: triggerScrape },
    { id: "week", label: "Generate week of posts", hint: "POST /posts/generate-week", icon: Megaphone, action: generateWeek },
  ];

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-[60] bg-black/70 backdrop-blur-md"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
          />
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
            className="fixed left-1/2 top-[15%] z-[61] w-[92%] max-w-xl -translate-x-1/2"
          >
            <Command
              label="Command palette"
              className="glass-strong overflow-hidden rounded-2xl"
            >
              <div className="flex items-center gap-2 border-b border-[hsl(var(--border))] px-4 py-3">
                <Search className="h-4 w-4 text-muted-foreground" />
                <Command.Input
                  placeholder="Search pages, actions, jobs..."
                  className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                />
                <kbd className="rounded border border-[hsl(var(--border))] bg-white/[0.04] px-1.5 py-0.5 text-[10px] mono text-muted-foreground">
                  ESC
                </kbd>
              </div>
              <Command.List className="max-h-[60vh] overflow-y-auto p-2">
                <Command.Empty className="py-8 text-center text-xs text-muted-foreground">
                  No results.
                </Command.Empty>
                <Command.Group heading="Navigate" className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-muted-foreground/70">
                  {nav.map((cmd) => (
                    <PaletteItem key={cmd.id} cmd={cmd} />
                  ))}
                </Command.Group>
                <Command.Group heading="Actions" className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-muted-foreground/70 [&_[cmdk-group-heading]]:mt-2">
                  {actions.map((cmd) => (
                    <PaletteItem key={cmd.id} cmd={cmd} />
                  ))}
                </Command.Group>
              </Command.List>
            </Command>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function PaletteItem({ cmd }: { cmd: NavCmd }) {
  const Icon = cmd.icon;
  return (
    <Command.Item
      value={`${cmd.label} ${cmd.hint}`}
      onSelect={cmd.action}
      className="group flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 text-sm text-foreground transition-colors data-[selected=true]:bg-[hsl(var(--accent-1))]/10 data-[selected=true]:text-[hsl(var(--accent-1))]"
    >
      <Icon className="h-4 w-4 text-muted-foreground group-data-[selected=true]:text-[hsl(var(--accent-1))]" />
      <span className="flex-1">{cmd.label}</span>
      <span className="text-[11px] text-muted-foreground">{cmd.hint}</span>
    </Command.Item>
  );
}
