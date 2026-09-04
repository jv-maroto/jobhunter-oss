"use client";

import * as React from "react";
import { Filter, RefreshCcw, ListChecks, Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { JobTable } from "@/components/jobs/JobTable";
import { useJobs } from "@/hooks/useJobs";
import { useScrapeStatus } from "@/hooks/useScrapeStatus";
import { api } from "@/lib/api";
import type { JobTrack } from "@/lib/types";
import { cn } from "@/lib/utils";

const SOURCES = ["all", "linkedin", "indeed", "remotive", "tecnoempleo", "jobspy-sysadmin"];
const STATUS_OPTIONS = ["detected", "prepared", "applied", "interviewing", "offer"];

export default function JobsPage() {
  const [track, setTrack] = React.useState<JobTrack>("dev");
  const [minScore, setMinScore] = React.useState(70);
  const [source, setSource] = React.useState<string>("all");
  const [status, setStatus] = React.useState<string>("detected");

  const jobs = useJobs({
    min_score: minScore,
    source: source === "all" ? undefined : source,
    status: status as never,
    track,
  });

  // Shared scrape status (persists across tab switches, polls in background,
  // shared with /today and any other page that reads the same key).
  const { running: scraping, refetch: refetchScrape } = useScrapeStatus();

  const triggerScrape = async () => {
    try {
      const res = await api<{ status: string }>("/jobs/scrape-now", {
        method: "POST",
      });
      if (res.status === "already_running") {
        toast.info("Scrape ya está en curso — espera al final.");
      } else {
        toast.success("Scrape lanzado en background", {
          description: "Se actualizará la lista cuando termine.",
        });
      }
      // Force immediate refetch so the button flips to "Scraping…" now.
      refetchScrape();
    } catch (e) {
      toast.error("Backend no disponible", {
        description: String(e).slice(0, 120),
      });
    }
  };

  const list = jobs.data ?? [];

  return (
    <div className="space-y-4">
      <Card variant="glass">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="inline-flex items-center gap-2">
              <ListChecks className="h-4 w-4 text-[hsl(var(--accent-1))]" />
              All jobs
            </CardTitle>
            <p className="text-[11px] text-muted-foreground mt-1">
              Track separado para Dev y SysAdmin. Por defecto solo se muestran ofertas
              <span className="mono"> detected</span> — cambia el filtro de status para ver el resto.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" size="sm" className="mono">
              {list.length} listed
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={triggerScrape}
              disabled={scraping}
            >
              {scraping ? (
                <Loader2 className="animate-spin" />
              ) : (
                <RefreshCcw />
              )}
              {scraping ? "Scraping…" : "Scrape now"}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Track tabs */}
          <div className="inline-flex rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--surface))]/60 p-1 w-full sm:w-auto">
            <TabButton active={track === "dev"} onClick={() => setTrack("dev")}>
              Dev / Full-Stack · AI
            </TabButton>
            <TabButton
              active={track === "sysadmin"}
              onClick={() => setTrack("sysadmin")}
            >
              SysAdmin · DevOps
            </TabButton>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground inline-flex items-center gap-1">
                <Filter className="h-3 w-3" />
                Status
              </label>
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((s) => (
                    <SelectItem key={s} value={s} className="capitalize">
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
                Source
              </label>
              <Select value={source} onValueChange={setSource}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SOURCES.map((s) => (
                    <SelectItem key={s} value={s} className="capitalize">
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground inline-flex items-center justify-between w-full">
                <span>Min match %</span>
                <span className="mono text-[hsl(var(--accent-1))]">
                  {minScore}
                </span>
              </label>
              <Slider
                value={[minScore]}
                onValueChange={(v) => setMinScore(v[0])}
                min={0}
                max={100}
                step={5}
              />
            </div>
          </div>

          {jobs.isLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <JobTable jobs={list} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex-1 sm:flex-initial px-4 py-2 text-xs font-medium rounded-lg transition-colors",
        active
          ? "bg-[hsl(var(--accent-1))]/15 text-[hsl(var(--accent-1))] border border-[hsl(var(--accent-1))]/40"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}
