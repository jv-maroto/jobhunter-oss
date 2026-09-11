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
import { useJobsPage } from "@/hooks/useJobs";
import { AddJobDialog } from "@/components/jobs/AddJobDialog";
import { useScrapeStatus } from "@/hooks/useScrapeStatus";
import { api } from "@/lib/api";
import { JOB_STATUSES, type JobStatus, type JobTrack } from "@/lib/types";
import { TrackFilter } from "@/components/jobs/TrackFilter";

const SOURCES = ["all", "manual", "linkedin", "indeed", "remotive", "tecnoempleo", "jobspy-sysadmin"];
const STATUS_OPTIONS = JOB_STATUSES;

export default function JobsPage() {
  const [track, setTrack] = React.useState<JobTrack | undefined>(undefined);
  const [minScore, setMinScore] = React.useState(0);
  const [source, setSource] = React.useState<string>("all");
  const [status, setStatus] = React.useState<JobStatus>("detected");
  const [offset, setOffset] = React.useState(0);

  // Debounce minScore so dragging the slider does not flood the backend
  // (each request rescores every job, so 6 concurrent requests block
  //  everything else including images).
  const [debouncedMinScore, setDebouncedMinScore] = React.useState(minScore);
  React.useEffect(() => {
    const id = window.setTimeout(() => setDebouncedMinScore(minScore), 400);
    return () => window.clearTimeout(id);
  }, [minScore]);

  const jobs = useJobsPage({
    min_score: debouncedMinScore,
    source: source === "all" ? undefined : source,
    status,
    track,
    limit: 50,
    offset,
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

  const list = jobs.data?.items ?? [];
  const total = jobs.data?.total ?? 0;

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
              Review evidence and requirements before preparing an application. Save postings from any board to keep them in your workspace.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" size="sm" className="mono">
              {total} jobs
            </Badge>
            <AddJobDialog />
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
          <TrackFilter value={track} onChange={(value) => { setTrack(value); setOffset(0); }} />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground inline-flex items-center gap-1">
                <Filter className="h-3 w-3" />
                Status
              </label>
              <Select value={status} onValueChange={(value) => { setStatus(value as JobStatus); setOffset(0); }}>
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
              <Select value={source} onValueChange={(value) => { setSource(value); setOffset(0); }}>
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
                <span>Min fit score</span>
                <span className="mono text-[hsl(var(--accent-1))]">
                  {minScore}
                </span>
              </label>
              <Slider
                value={[minScore]}
                onValueChange={(v) => { setMinScore(v[0]); setOffset(0); }}
                min={0}
                max={100}
                step={5}
              />
            </div>
          </div>

          {jobs.data ? (
            // We already have data (fresh or stale). Show the table always —
            // never blank it out when the user comes back to the page.
            <>
              {jobs.isFetching && (
                <div className="mb-2 inline-flex items-center gap-2 rounded-md border border-[hsl(var(--border))] bg-background/60 px-2.5 py-1 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Actualizando…
                </div>
              )}
              <JobTable jobs={list} />
            </>
          ) : jobs.error ? (
            <p role="alert" className="text-sm text-rose-400">No se pudieron cargar las ofertas. <button className="underline" onClick={() => void jobs.refetch()}>Reintentar</button></p>
          ) : (
            // Absolute first load — no cached data yet.
            <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-[hsl(var(--border))] bg-background/40">
              <Loader2 className="h-7 w-7 animate-spin text-[hsl(var(--accent-1))]" />
              <p className="text-sm font-medium text-foreground">Cargando trabajos…</p>
              <p className="text-xs text-muted-foreground">
                Consultando la base de datos y aplicando filtros
              </p>
            </div>
          )}
          {total > 50 && <div className="flex justify-between items-center gap-3 text-sm">
            <span>{offset + 1}–{Math.min(offset + list.length, total)} of {total}</span>
            <div className="flex gap-2"><Button variant="outline" disabled={offset === 0 || jobs.isFetching} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</Button><Button variant="outline" disabled={offset + 50 >= total || jobs.isFetching} onClick={() => setOffset(offset + 50)}>Next</Button></div>
          </div>}
        </CardContent>
      </Card>
    </div>
  );
}
