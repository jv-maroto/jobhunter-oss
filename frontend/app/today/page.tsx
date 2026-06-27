"use client";

import * as React from "react";
import {
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
import { api } from "@/lib/api";
import { cn, formatEur } from "@/lib/utils";

const SOURCES = ["all", "linkedin", "indeed", "remotive", "tecnoempleo"];

export default function TodayPage() {
  const [minScore, setMinScore] = React.useState(30);
  const [source, setSource] = React.useState<string>("all");

  const jobs = useJobs({
    min_score: minScore,
    source: source === "all" ? undefined : source,
  });
  const persons = usePersons("pending");
  const metrics = useMetricsToday();
  const hasPaidApi = useHasPaidApi();

  const detected = (jobs.data ?? []).filter((j) => j.status === "detected");
  const fresh = detected.slice().sort(
    (a, b) => (b.match_score ?? 0) - (a.match_score ?? 0),
  );
  // Histogram for visibility
  const bucket = (lo: number, hi: number) =>
    detected.filter(
      (j) => (j.match_score ?? 0) >= lo && (j.match_score ?? 0) <= hi,
    ).length;
  const dist = {
    excellent: bucket(90, 100),
    strong: bucket(70, 89),
    maybe: bucket(50, 69),
    stretch: bucket(30, 49),
    skip: bucket(0, 29),
  };

  const triggerScrape = async () => {
    try {
      const res = await api<{
        scraped?: number;
        inserted?: number;
        duplicates?: number;
      }>("/jobs/scrape-now", { method: "POST" });
      const scraped = res?.scraped ?? 0;
      const inserted = res?.inserted ?? 0;
      const dupes = res?.duplicates ?? 0;
      toast.success(`Scrape: ${scraped} found, ${inserted} new`, {
        description:
          dupes > 0
            ? `${dupes} duplicates already in DB (including any you previously skipped).`
            : undefined,
        icon: <RefreshCcw className="h-4 w-4" />,
        duration: 6000,
      });
      jobs.refetch();
      metrics.refetch();
    } catch (e) {
      toast.error("Backend offline — scrape skipped", {
        description: String(e).slice(0, 120),
      });
    }
  };

  const m = metrics.data;

  return (
    <div className="space-y-5">
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
          value={m?.today.new_jobs ?? 0}
          hint="today"
          icon={Briefcase}
          delta={12.5}
          spark={[3, 5, 4, 6, 8, 7, 9]}
          accent={m && m.today.new_jobs > 0 ? "default" : "warn"}
        />
        <MetricCard
          label="Above 70"
          value={m?.today.jobs_above_70 ?? 0}
          hint="strong matches"
          icon={Target}
          delta={4.2}
          spark={[1, 2, 1, 3, 4, 3, 5]}
          accent="good"
        />
        <MetricCard
          label="Connects"
          value={(persons.data ?? []).length}
          hint="pending outreach"
          icon={Users}
          spark={[2, 3, 4, 3, 5, 4, 6]}
        />
        {hasPaidApi && (
          <MetricCard
            label="API today"
            value={formatEur(m?.api_cost_eur.today ?? 0)}
            hint={`month ${formatEur(m?.api_cost_eur.month ?? 0)}`}
            icon={CircleDollarSign}
            delta={-8.4}
            positiveIsGood={false}
            spark={[0.2, 0.4, 0.3, 0.5, 0.6, 0.4, 0.42]}
          />
        )}
      </motion.div>

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
                  Filtered by score and source — click Prepare to materialize CV + cover letter.
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={triggerScrape}>
                <RefreshCcw />
                Trigger
              </Button>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-4 items-end">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] font-medium uppercase tracking-wider inline-flex items-center gap-1.5 text-muted-foreground">
                      <Filter className="h-3 w-3" />
                      Min score
                    </label>
                    <span className="mono text-xs text-[hsl(var(--accent-1))]">
                      {minScore}
                    </span>
                  </div>
                  <Slider
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
                    <SelectTrigger className="mt-1.5">
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

              {/* Score distribution histogram */}
              {!jobs.isLoading && detected.length > 0 && (
                <div className="flex items-center gap-1.5 text-[10px] mono flex-wrap">
                  <span className="text-muted-foreground/70 uppercase tracking-wider">
                    Pool:
                  </span>
                  <span
                    className="rounded-full px-2 py-0.5 bg-[hsl(var(--score-good))]/15 text-[hsl(var(--score-good))] border border-[hsl(var(--score-good))]/30"
                    title="Score 90-100"
                  >
                    {dist.excellent} excellent
                  </span>
                  <span
                    className="rounded-full px-2 py-0.5 bg-[hsl(var(--score-good))]/10 text-[hsl(var(--score-good))]/90 border border-[hsl(var(--score-good))]/20"
                    title="Score 70-89"
                  >
                    {dist.strong} strong
                  </span>
                  <span
                    className="rounded-full px-2 py-0.5 bg-[hsl(var(--score-mid))]/12 text-[hsl(var(--score-mid))] border border-[hsl(var(--score-mid))]/30"
                    title="Score 50-69"
                  >
                    {dist.maybe} maybe
                  </span>
                  <span
                    className="rounded-full px-2 py-0.5 bg-[hsl(var(--score-mid))]/8 text-[hsl(var(--score-mid))]/80 border border-[hsl(var(--score-mid))]/15"
                    title="Score 30-49 — stretch, niche fit"
                  >
                    {dist.stretch} stretch
                  </span>
                  <span
                    className="rounded-full px-2 py-0.5 bg-muted/30 text-muted-foreground/60 border border-[hsl(var(--border))]"
                    title="Score 0-29 — not aligned"
                  >
                    {dist.skip} skip
                  </span>
                </div>
              )}

              {jobs.isLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                </div>
              ) : fresh.length === 0 ? (
                <div className="rounded-xl border border-dashed border-[hsl(var(--border))] p-10 text-center space-y-3">
                  <p className="text-sm text-muted-foreground">
                    No jobs detected matching your filters.
                  </p>
                  <Button onClick={triggerScrape} shimmer>
                    <RefreshCcw />
                    Trigger scrape
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
                Pre-drafted DMs, prioritised by relevance.
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              {persons.isLoading ? (
                <Skeleton className="h-32 w-full" />
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
