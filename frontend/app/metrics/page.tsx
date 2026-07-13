"use client";

import {
  Briefcase,
  CircleDollarSign,
  Send,
  Sparkles,
  Users,
  Cpu,
  Activity,
} from "lucide-react";
import { MetricCard } from "@/components/metrics/MetricCard";
import {
  AppsBySourceChart,
  JobsPerDayChart,
  PipelinePieChart,
  TopCompaniesChart,
  ApiCostByProviderChart,
  ApiCostSparkline,
} from "@/components/metrics/charts/Charts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompanies, useMetricsToday, usePipeline } from "@/hooks/useMetrics";
import { useJobs } from "@/hooks/useJobs";
import { usePersons } from "@/hooks/usePersons";
import { useApiCosts } from "@/hooks/useApiCosts";
import { useHasPaidApi } from "@/hooks/useAiSettings";
import { JOB_STATUSES, type Job } from "@/lib/types";
import { cn, formatEur, formatRelative } from "@/lib/utils";

/** Serie "jobs detectados por día" (últimos 30 días) derivada de datos reales. */
function buildJobsPerDay(jobs: Job[]) {
  const days: { key: string; date: string }[] = [];
  const index = new Map<string, number>();
  for (let i = 29; i >= 0; i--) {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    days.push({
      key,
      date: d.toLocaleDateString("es-ES", { day: "2-digit", month: "short" }),
    });
    index.set(key, days.length - 1);
  }
  const detected = new Array(days.length).fill(0);
  const high = new Array(days.length).fill(0);
  for (const j of jobs) {
    const key = (j.posted_at ?? "").slice(0, 10);
    const i = index.get(key);
    if (i === undefined) continue;
    detected[i] += 1;
    if (j.match_score >= 70) high[i] += 1;
  }
  return days.map((d, i) => ({
    date: d.date,
    detected: detected[i],
    high_match: high[i],
  }));
}

/** Recuento de ofertas por fuente derivado de datos reales. */
function buildAppsBySource(jobs: Job[]) {
  const counts = new Map<string, number>();
  for (const j of jobs) {
    const src = j.source || "unknown";
    counts.set(src, (counts.get(src) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([source, count]) => ({ source, count }))
    .sort((a, b) => b.count - a.count);
}

export default function MetricsPage() {
  const metrics = useMetricsToday();
  const pipeline = usePipeline();
  const companies = useCompanies();
  const jobs = useJobs();
  const persons = usePersons();
  const apiCosts = useApiCosts();
  const hasPaidApi = useHasPaidApi();

  if (metrics.isLoading || !metrics.data || !pipeline.data) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );
  }

  const m = metrics.data;
  const weekScraped = (jobs.data ?? []).length;
  const totalApplied =
    pipeline.data.applied.length +
    pipeline.data.interviewing.length +
    pipeline.data.offer.length +
    pipeline.data.rejected.length +
    pipeline.data.ghosted.length;
  const responses =
    pipeline.data.interviewing.length +
    pipeline.data.offer.length +
    pipeline.data.rejected.length;
  const responseRate =
    totalApplied > 0 ? Math.round((responses / totalApplied) * 100) : 0;

  const pipelineDist = JOB_STATUSES.map((s) => ({
    name: s,
    value: pipeline.data![s].length,
  }));

  const topCompanies = (companies.data ?? [])
    .slice()
    .sort((a, b) => b.avg_score - a.avg_score)
    .slice(0, 10)
    .map((c) => ({
      company: c.name ?? c.company ?? "—",
      avg_score: c.avg_score,
    }));

  const allJobs = jobs.data ?? [];
  const jobsPerDay = buildJobsPerDay(allJobs);
  const appsBySource = buildAppsBySource(allJobs);
  const acceptedConnections = (persons.data ?? []).filter(
    (p) => p.status === "accepted",
  ).length;

  const costs = apiCosts.data;

  return (
    <div className="space-y-6">
      {/* Activity row */}
      <section>
        <h2 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-3">
          Activity
        </h2>
        <div
          className={cn(
            "grid grid-cols-2 sm:grid-cols-3 gap-3",
            hasPaidApi ? "lg:grid-cols-5" : "lg:grid-cols-4",
          )}
        >
          <MetricCard
            label="Jobs scraped"
            value={weekScraped}
            hint="this week"
            icon={Briefcase}
          />
          <MetricCard
            label="Applications"
            value={totalApplied}
            hint="all time"
            icon={Send}
          />
          <MetricCard
            label="Response rate"
            value={`${responseRate}%`}
            hint={`${responses}/${totalApplied}`}
            icon={Sparkles}
            accent="good"
          />
          <MetricCard
            label="Connections"
            value={acceptedConnections}
            hint="LinkedIn accepted"
            icon={Users}
          />
          {hasPaidApi && (
            <MetricCard
              label="API cost"
              value={formatEur(m.api_cost_eur.month)}
              hint={`today ${formatEur(m.api_cost_eur.today)}`}
              icon={CircleDollarSign}
              positiveIsGood={false}
            />
          )}
        </div>
      </section>

      <section>
        <h2 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-3">
          Distribution
        </h2>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <JobsPerDayChart data={jobsPerDay} />
          <AppsBySourceChart data={appsBySource} />
          <PipelinePieChart data={pipelineDist} />
          <TopCompaniesChart data={topCompanies} />
        </div>
      </section>

      {hasPaidApi && (
      <section>
        <h2 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-3">
          AI Provider Cost
        </h2>
        {apiCosts.isLoading || !costs ? (
          <Skeleton className="h-72 w-full" />
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <MetricCard
                label="Today"
                value={formatEur(costs.total_today_eur)}
                hint={`${costs.by_provider.reduce((s, p) => s + p.calls_today, 0)} calls`}
                icon={CircleDollarSign}
                accent={costs.total_today_eur > 1 ? "warn" : "default"}
              />
              <MetricCard
                label="Month so far"
                value={formatEur(costs.total_month_eur)}
                hint={`${costs.by_provider.reduce((s, p) => s + p.calls_month, 0)} calls`}
                icon={CircleDollarSign}
                positiveIsGood={false}
              />
              <ApiCostSparkline
                data={costs.daily}
                label="Last 30 days · €/day"
              />
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <ApiCostByProviderChart
                data={costs.by_provider.map((b) => ({
                  provider: b.provider,
                  cost_today_eur: b.cost_today_eur,
                  cost_month_eur: b.cost_month_eur,
                }))}
              />
              <Card variant="glass">
                <CardHeader>
                  <CardTitle className="inline-flex items-center gap-2">
                    <Cpu className="h-4 w-4 text-[hsl(var(--accent-1))]" />
                    Per-provider breakdown
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Provider</TableHead>
                        <TableHead className="text-right">Today</TableHead>
                        <TableHead className="text-right">Month</TableHead>
                        <TableHead className="text-right">Latency</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {costs.by_provider.map((b) => (
                        <TableRow key={b.provider}>
                          <TableCell className="capitalize">
                            <span className="inline-flex items-center gap-2">
                              <span
                                className="h-1.5 w-1.5 rounded-full"
                                style={{
                                  background:
                                    b.provider === "anthropic"
                                      ? "hsl(187 92% 49%)"
                                      : b.provider === "gemini"
                                        ? "hsl(75 85% 60%)"
                                        : b.provider === "ollama"
                                          ? "hsl(142 71% 45%)"
                                          : "hsl(38 95% 55%)",
                                }}
                              />
                              {b.provider}
                            </span>
                          </TableCell>
                          <TableCell className="text-right mono text-xs">
                            {formatEur(b.cost_today_eur)}
                          </TableCell>
                          <TableCell className="text-right mono text-xs">
                            {formatEur(b.cost_month_eur)}
                          </TableCell>
                          <TableCell className="text-right mono text-xs text-muted-foreground">
                            {b.avg_latency_ms}ms
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>

            <Card variant="glass">
              <CardHeader>
                <CardTitle className="inline-flex items-center gap-2">
                  <Activity className="h-4 w-4 text-[hsl(var(--accent-1))]" />
                  Recent API calls
                </CardTitle>
                <p className="text-[11px] text-muted-foreground">
                  Last 20 calls across all providers.
                </p>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>When</TableHead>
                      <TableHead>Provider</TableHead>
                      <TableHead>Model</TableHead>
                      <TableHead>Endpoint</TableHead>
                      <TableHead className="text-right">Tokens</TableHead>
                      <TableHead className="text-right">Lat.</TableHead>
                      <TableHead className="text-right">€</TableHead>
                      <TableHead>OK</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {costs.recent_calls.map((c) => (
                      <TableRow key={c.id}>
                        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                          {formatRelative(c.created_at)}
                        </TableCell>
                        <TableCell className="capitalize">
                          <Badge variant="mono" size="sm">
                            {c.provider}
                          </Badge>
                        </TableCell>
                        <TableCell className="mono text-xs">{c.model}</TableCell>
                        <TableCell className="mono text-xs text-muted-foreground">
                          {c.endpoint}
                        </TableCell>
                        <TableCell className="text-right mono text-xs text-muted-foreground">
                          {c.tokens_in}/{c.tokens_out}
                        </TableCell>
                        <TableCell className="text-right mono text-xs">
                          {c.latency_ms}ms
                        </TableCell>
                        <TableCell className="text-right mono text-xs">
                          {formatEur(c.cost_eur)}
                        </TableCell>
                        <TableCell>
                          {c.ok ? (
                            <Badge variant="success" size="sm">
                              ok
                            </Badge>
                          ) : (
                            <Badge variant="urgent" size="sm">
                              err
                            </Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        )}
      </section>
      )}
    </div>
  );
}
