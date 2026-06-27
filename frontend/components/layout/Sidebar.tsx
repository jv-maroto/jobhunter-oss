"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Sparkles,
  KanbanSquare,
  BarChart3,
  Building2,
  ContactRound,
  Settings,
  Briefcase,
  Command,
  FileText,
  ListChecks,
  Globe,
} from "lucide-react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";
import { useBackendStatus } from "@/hooks/useBackendStatus";
import { useMetricsToday } from "@/hooks/useMetrics";
import { usePersons } from "@/hooks/usePersons";
import { commandPaletteStore } from "@/components/layout/CommandPalette";

interface NavItem {
  href: string;
  label: string;
  icon: typeof Sparkles;
  /** Optional badge resolver */
  badge?: (ctx: { newJobs: number; persons: number }) => number | undefined;
}

const NAV: NavItem[] = [
  {
    href: "/today",
    label: "Today",
    icon: Sparkles,
    badge: (c) => (c.newJobs > 0 ? c.newJobs : undefined),
  },
  { href: "/jobs", label: "Jobs", icon: ListChecks },
  { href: "/pipeline", label: "Pipeline", icon: KanbanSquare },
  { href: "/applications", label: "Applications", icon: FileText },
  { href: "/metrics", label: "Metrics", icon: BarChart3 },
  { href: "/companies", label: "Companies", icon: Building2 },
  {
    href: "/linkedin",
    label: "LinkedIn",
    icon: ContactRound,
    badge: (c) => (c.persons > 0 ? c.persons : undefined),
  },
  { href: "/settings/search", label: "Búsqueda", icon: Globe },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const status = useBackendStatus();
  const metrics = useMetricsToday();
  const persons = usePersons("pending");
  const connected = status.data === true;
  const newJobs = metrics.data?.today.new_jobs ?? 0;
  const pendingPersons = (persons.data ?? []).length;

  const itemBase =
    "relative flex h-10 items-center rounded-lg text-sm transition-all " +
    "justify-center group-hover/sidebar:justify-start " +
    "group-hover/sidebar:px-3 group-hover/sidebar:gap-2.5";

  return (
    <aside className="hidden md:flex fixed left-0 top-0 z-50 h-screen flex-col p-2 group/sidebar">
      <div className="glass-strong flex h-full flex-col rounded-2xl py-3 hover:w-[212px] hover:shadow-[0_0_50px_-12px_hsl(var(--accent-1)/0.25)] w-[60px] transition-[width,box-shadow] duration-300 ease-out overflow-hidden">
        {/* Logo */}
        <Link
          href="/today"
          className={cn(
            itemBase,
            "mx-1.5 mb-2 hover:bg-white/5",
          )}
        >
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-gradient-to-br from-[hsl(var(--accent-1))] to-[hsl(var(--accent-2))] text-[hsl(var(--primary-foreground))] shadow-[0_4px_16px_-4px_hsl(var(--accent-1)/0.6)]">
            <Briefcase className="h-4 w-4" />
          </div>
          <div className="leading-tight whitespace-nowrap hidden group-hover/sidebar:flex flex-col">
            <div className="text-sm font-semibold font-[family-name:var(--font-display)]">
              JobHunter
            </div>
            <div className="text-[9px] uppercase tracking-[0.15em] text-muted-foreground">
              Command Center
            </div>
          </div>
        </Link>

        <div className="hr-grad mx-3 my-1" />

        {/* Command palette trigger */}
        <button
          type="button"
          onClick={() => commandPaletteStore.open()}
          className={cn(
            itemBase,
            "mx-1.5 my-1 text-xs text-muted-foreground hover:bg-white/5 hover:text-foreground",
          )}
        >
          <Command className="h-4 w-4 shrink-0" />
          <span className="whitespace-nowrap hidden group-hover/sidebar:flex">
            Search
          </span>
          <kbd className="hidden group-hover/sidebar:inline-flex ml-auto rounded border border-[hsl(var(--border))] bg-white/[0.04] px-1.5 py-0.5 text-[9px] mono">
            ⌘K
          </kbd>
        </button>

        <nav className="flex-1 flex-col px-1.5 flex">
          {NAV.map(({ href, label, icon: Icon, badge }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            const badgeValue = badge?.({ newJobs, persons: pendingPersons });
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  itemBase,
                  "mb-0.5",
                  active
                    ? "bg-white/5 text-foreground"
                    : "text-muted-foreground hover:bg-white/5 hover:text-foreground",
                )}
              >
                {active && (
                  <motion.span
                    layoutId="nav-rail"
                    className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-gradient-to-b from-[hsl(var(--accent-1))] to-[hsl(var(--accent-2))]"
                    style={{
                      boxShadow: "0 0 10px hsl(var(--accent-1))",
                    }}
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0 transition-colors",
                    active && "text-[hsl(var(--accent-1))]",
                  )}
                />
                <span className="whitespace-nowrap hidden group-hover/sidebar:flex">
                  {label}
                </span>
                {badgeValue !== undefined && (
                  <span
                    className={cn(
                      "ml-auto hidden group-hover/sidebar:flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-mono shrink-0",
                      "bg-[hsl(var(--accent-1))]/15 text-[hsl(var(--accent-1))] border border-[hsl(var(--accent-1))]/30",
                    )}
                  >
                    {badgeValue}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        <div className="hr-grad mx-3 my-1" />

        {/* Backend status */}
        <div
          className={cn(
            itemBase,
            "mx-1.5 mb-1 cursor-default",
          )}
        >
          <span
            className={cn(
              "dot-live shrink-0",
              connected
                ? "bg-[hsl(var(--score-good))]"
                : "bg-[hsl(var(--accent-warn))]",
            )}
          />
          <div className="flex-1 leading-tight whitespace-nowrap hidden group-hover/sidebar:flex">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Backend
            </div>
            <div
              className={cn(
                "text-xs font-medium",
                connected
                  ? "text-[hsl(var(--score-good))]"
                  : "text-[hsl(var(--accent-warn))]",
              )}
            >
              {connected ? "online" : "offline"}
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
