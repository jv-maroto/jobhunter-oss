"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { ChevronRight, RadioTower } from "lucide-react";
import { useMetricsToday } from "@/hooks/useMetrics";
import { usePersons } from "@/hooks/usePersons";
import { ThemeToggle } from "./ThemeToggle";
import { useBackendStatus } from "@/hooks/useBackendStatus";
import { useHasPaidApi } from "@/hooks/useAiSettings";
import { cn, formatEur } from "@/lib/utils";

const TITLES: Record<string, { title: string; sub: string }> = {
  "/today": {
    title: "Today",
    sub: "Fresh detections + LinkedIn outreach",
  },
  "/jobs": {
    title: "Jobs",
    sub: "All detected jobs in a full table",
  },
  "/pipeline": {
    title: "Pipeline",
    sub: "Move jobs through stages",
  },
  "/applications": {
    title: "Applications",
    sub: "Generated CVs and cover letters",
  },
  "/metrics": {
    title: "Metrics",
    sub: "Activity, cost and conversion",
  },
  "/companies": {
    title: "Companies",
    sub: "Aggregated employer view",
  },
  "/networking": {
    title: "Networking",
    sub: "Sugerencias y contactos",
  },
  "/settings": {
    title: "Settings",
    sub: "Identity, theme, AI",
  },
};

export function TopBar() {
  const pathname = usePathname();
  const entry =
    Object.entries(TITLES).find(([k]) => pathname.startsWith(k))?.[1] ?? {
      title: "Dashboard",
      sub: "",
    };
  const { data } = useMetricsToday();
  const persons = usePersons("pending");
  const status = useBackendStatus();
  const connected = status.data === true;
  const hasPaidApi = useHasPaidApi();

  const newJobs = data?.today.new_jobs ?? 0;
  const prepared = data?.today.applications_prepared ?? 0;
  const connections = (persons.data ?? []).length;
  const apiToday = data?.api_cost_eur.today ?? 0;

  return (
    <header className="sticky top-0 z-30">
      <div className="flex min-h-16 items-center justify-between gap-4 px-5 lg:px-6 py-2 border-b border-[hsl(var(--border))] backdrop-blur-xl bg-[hsl(var(--background))]/70">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <Link
            href="/today"
            className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground hover:text-foreground transition-colors hidden sm:inline shrink-0"
          >
            JobSlaves
          </Link>
          <ChevronRight className="h-3 w-3 text-muted-foreground hidden sm:block shrink-0" />
          <div className="min-w-0 flex-1">
            <h1 className="text-base font-semibold leading-tight font-[family-name:var(--font-display)] truncate">
              {entry.title}
            </h1>
            {entry.sub && (
              <p className="mt-0.5 text-[11px] text-muted-foreground truncate">
                {entry.sub}
              </p>
            )}
          </div>
        </div>

        {/* Live metrics strip */}
        <div className="hidden lg:flex items-center gap-3 mono text-[11px] text-muted-foreground">
          <Metric label="JOBS" value={newJobs} accent={newJobs > 0} />
          <Sep />
          <Metric label="PREPARED" value={prepared} />
          <Sep />
          <Metric label="CONNECT" value={connections} accent={connections > 0} />
          {hasPaidApi && (
            <>
              <Sep />
              <Metric
                label="API"
                value={formatEur(apiToday)}
                mono
                accent={apiToday > 1}
              />
            </>
          )}
        </div>

        <div className="flex items-center gap-2">
          <div
            className={cn(
              "hidden md:flex items-center gap-2 rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-wider transition-colors",
              connected
                ? "border-[hsl(var(--score-good))]/30 text-[hsl(var(--score-good))]"
                : "border-[hsl(var(--accent-warn))]/35 text-[hsl(var(--accent-warn))]",
            )}
          >
            <RadioTower className="h-3 w-3" />
            {connected ? "live" : "offline"}
          </div>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

function Metric({
  label,
  value,
  accent,
  mono = false,
}: {
  label: string;
  value: number | string;
  accent?: boolean;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[9px] uppercase tracking-[0.15em] text-muted-foreground/70">
        {label}
      </span>
      <span
        className={cn(
          mono && "mono",
          "text-foreground tabular-nums",
          accent && "text-[hsl(var(--accent-1))]",
        )}
      >
        {value}
      </span>
    </div>
  );
}

function Sep() {
  return <span className="text-muted-foreground/30">·</span>;
}
