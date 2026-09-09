"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Clock3,
  Filter,
  RefreshCcw,
  Sparkles,
  Users,
  Briefcase,
  CircleDollarSign,
  Target,
} from "lucide-react";
import { toast } from "sonner";
import { motion } from "motion/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { JobsCompactList } from "@/components/jobs/JobsCompactList";
import { PersonCard } from "@/components/persons/PersonCard";
import { MetricCard } from "@/components/metrics/MetricCard";
import { useJobs } from "@/hooks/useJobs";
import { usePersons } from "@/hooks/usePersons";
import { useMetricsToday } from "@/hooks/useMetrics";
import { useHasPaidApi } from "@/hooks/useAiSettings";
import { useApplications } from "@/hooks/useApplications";
import { useScrapeStatus } from "@/hooks/useScrapeStatus";
import { api } from "@/lib/api";
import { apiDate, cn, formatEur } from "@/lib/utils";

const SOURCES = ["all", "linkedin", "indeed", "remotive", "tecnoempleo"];

export default function TodayPage() {
  const [minScore, setMinScore] = React.useState(30);
  const [source, setSource] = React.useState<string>("all");
  const [dueBefore, setDueBefore] = React.useState(() => new Date().toISOString());
  const [startingScrape, setStartingScrape] = React.useState(false);

  React.useEffect(() => {
    const timer = window.setInterval(() => setDueBefore(new Date().toISOString()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const jobs = useJobs({
    status: "detected",
    min_score: minScore,
    source: source === "all" ? undefined : source,
  });
  const persons = usePersons("pending");
  const metrics = useMetricsToday();
  const hasPaidApi = useHasPaidApi();
  const due = useApplications({ due_before: dueBefore, limit: 8 });
  const { running: scraping, refetch: refetchScrape } = useScrapeStatus();
  const scrapeBusy = startingScrape || scraping;

  const detected = (jobs.data ?? []).filter((j) => j.status === "detected");
  const fresh = detected.slice().sort(
    (a, b) => (b.match_score ?? 0) - (a.match_score ?? 0),
  );
  const triggerScrape = async () => {
    setStartingScrape(true);
    try {
      const result = await api<{ status: string }>("/jobs/scrape-now", { method: "POST" });
      toast.info(result.status === "already_running" ? "Discovery is already running" : "Discovery started", {
        description: "The list updates when discovery finishes.",
      });
      await refetchScrape();
    } catch (e) {
      toast.error("Could not start discovery", {
        description: String(e).slice(0, 120),
      });
    } finally {
      setStartingScrape(false);
    }
  };

  const m = metrics.data;

  return (
    <div className="space-y-5">
      <Card variant="glass">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <CardTitle className="inline-flex items-center gap-2">
              <Clock3 className="h-4 w-4 text-[hsl(var(--accent-1))]" />
              Due follow-ups
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              Scheduled next actions due now or overdue, earliest first. Refreshes every minute.
            </p>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link href="/applications">View applications <ArrowRight /></Link>
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {due.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : due.isError ? (
            <div role="alert" className="space-y-2 text-sm">
              <p>Could not load due follow-ups.</p>
              <Button variant="outline" size="sm" onClick={() => due.refetch()}>Retry</Button>
            </div>
          ) : !due.data?.items.length ? (
            <p className="rounded-lg border border-dashed border-[hsl(var(--border))] p-6 text-sm text-muted-foreground">
              No follow-ups due right now. Set a next action and date on a job to bring it here.
            </p>
          ) : (
            <>
              <ul className="divide-y divide-[hsl(var(--border))] rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--surface))]/40">
                {due.data.items.map((item) => {
                  const dueAt = apiDate(item.job.next_action_at);
                  return (
                    <li key={item.job.id}>
                      <Link
                        href={item.application_id !== null ? `/applications/${item.application_id}` : `/jobs/${item.job.id}`}
                        className="row-hover flex items-center gap-3 rounded-lg px-4 py-3 focus-visible:outline-2 focus-visible:outline-[hsl(var(--accent-1))]"
                      >
                        <div className="min-w-0 flex-1 space-y-1">
                          <p className="break-words text-sm font-medium">{item.job.next_action || "Review next step"}</p>
                          <p className="break-words text-xs text-muted-foreground">{item.job.title || "Untitled job"} · {item.job.company || "Company unavailable"}</p>
                          <time dateTime={dueAt?.toISOString()} className="block text-xs text-muted-foreground">
                            {dueAt ? dueAt.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "Due date unavailable"}
                          </time>
                        </div>
                        <ArrowRight aria-hidden className="h-4 w-4 shrink-0 text-muted-foreground" />
                      </Link>
                    </li>
                  );
                })}
              </ul>
              <p className="text-xs text-muted-foreground">
                Showing {due.data.items.length} of {due.data.total} due follow-ups.
              </p>
            </>
          )}
        </CardContent>
      </Card>

      {/* MIDI bento: live metric strip */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className={cn(
          "grid grid-cols-2 gap-3",
          hasPaidApi ? "lg:grid-cols-4" : "lg:grid-cols-3",
        )}
      >
        <MetricCard
          label="New jobs"
          value={metrics.isError ? "—" : m?.today.new_jobs ?? "—"}
          hint={metrics.isError ? "unavailable" : metrics.isLoading ? "loading…" : "today"}
          icon={Briefcase}
          accent={m && m.today.new_jobs > 0 ? "default" : "warn"}
        />
        <MetricCard
          label="Fit score ≥70"
          value={metrics.isError ? "—" : m?.today.jobs_above_70 ?? "—"}
          hint={metrics.isError ? "unavailable" : metrics.isLoading ? "loading…" : "detected jobs"}
          icon={Target}
          accent="good"
        />
        <MetricCard
          label="Connects"
          value={persons.isError ? "—" : persons.data?.length ?? "—"}
          hint={persons.isError ? "unavailable" : persons.isLoading ? "loading…" : "pending outreach"}
          icon={Users}
        />
        {hasPaidApi && (
          <MetricCard
            label="API today"
            value={m && !metrics.isError ? formatEur(m.api_cost_eur.today) : "—"}
            hint={metrics.isError ? "unavailable" : m ? `month ${formatEur(m.api_cost_eur.month)}` : "loading…"}
            icon={CircleDollarSign}
            positiveIsGood={false}
          />
        )}
      </motion.div>
      {metrics.isError && (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          Today&apos;s metrics could not be loaded.
          <Button variant="outline" size="sm" onClick={() => metrics.refetch()}>Retry metrics</Button>
        </div>
      )}

      {/* Bento grid: left = jobs (3 cols), right = outreach stack (2 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        <section className="lg:col-span-3">
          <Card variant="glass">
            <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
              <div>
                <CardTitle className="inline-flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-[hsl(var(--accent-1))]" />
                  Fresh detections
                </CardTitle>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Fit scores help prioritize review; they do not predict hiring outcomes. Review the job before preparing documents.
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={triggerScrape} disabled={scrapeBusy}>
                <RefreshCcw className={scrapeBusy ? "animate-spin" : undefined} />
                {scrapeBusy ? "Discovering…" : "Discover jobs"}
              </Button>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-4 items-end">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] font-medium uppercase tracking-wider inline-flex items-center gap-1.5 text-muted-foreground">
                      <Filter className="h-3 w-3" />
                      Min fit score
                    </label>
                    <span className="mono text-xs text-[hsl(var(--accent-1))]">
                      {minScore}
                    </span>
                  </div>
                  <Slider
                    aria-label="Minimum fit score"
                    min={0}
                    max={100}
                    step={1}
                    value={[minScore]}
                    onValueChange={(v) => setMinScore(v[0] ?? 0)}
                  />
                </div>
                <div className="min-w-[180px]">
                  <label className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                    Source
                  </label>
                  <Select value={source} onValueChange={setSource}>
                    <SelectTrigger className="mt-1.5" aria-label="Job source">
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
              </div>

              {jobs.isLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                </div>
              ) : jobs.isError ? (
                <div role="alert" className="space-y-2 text-sm">
                  <p>Could not load detected jobs.</p>
                  <Button variant="outline" size="sm" onClick={() => jobs.refetch()}>Retry</Button>
                </div>
              ) : fresh.length === 0 ? (
                <div className="rounded-xl border border-dashed border-[hsl(var(--border))] p-10 text-center space-y-3">
                  <p className="text-sm text-muted-foreground">
                    No jobs detected matching your filters.
                  </p>
                  <p className="text-xs text-muted-foreground">Try a lower fit score or another source, or discover new jobs.</p>
                  <Button onClick={triggerScrape} shimmer disabled={scrapeBusy}>
                    <RefreshCcw className={scrapeBusy ? "animate-spin" : undefined} />
                    {scrapeBusy ? "Discovering…" : "Discover jobs"}
                  </Button>
                </div>
              ) : (
                <JobsCompactList jobs={fresh} limit={8} />
              )}
            </CardContent>
          </Card>
        </section>

        <section className="lg:col-span-2 space-y-4">
          <Card variant="glass">
            <CardHeader>
              <CardTitle className="inline-flex items-center gap-2">
                <Users className="h-4 w-4 text-[hsl(var(--accent-1))]" />
                People to connect
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                Review pending contacts and any available message drafts before reaching out.
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              {persons.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : persons.isError ? (
                <div role="alert" className="space-y-2 text-sm">
                  <p>Could not load pending contacts.</p>
                  <Button variant="outline" size="sm" onClick={() => persons.refetch()}>Retry</Button>
                </div>
              ) : (persons.data ?? []).length === 0 ? (
                <div className="rounded-lg border border-dashed border-[hsl(var(--border))] p-6 text-center text-xs text-muted-foreground">
                  No pending connections.
                </div>
              ) : (
                (persons.data ?? []).slice(0, 3).map((p) => (
                  <PersonCard key={p.id} person={p} />
                ))
              )}
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
