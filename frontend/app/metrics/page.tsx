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
import { useApiCosts } from "@/hooks/useApiCosts";
import {
  mockAppsBySource,
  mockJobsPerDay,
  mockApiCostsPerDay,
} from "@/lib/mock";
import { JOB_STATUSES } from "@/lib/types";
import { formatEur, formatRelative } from "@/lib/utils";

export default function MetricsPage() {
  const metrics = useMetricsToday();
  const pipeline = usePipeline();
  const companies = useCompanies();
  const jobs = useJobs();
  const apiCosts = useApiCosts();

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

  const costs = apiCosts.data;

  return (
    <div className="space-y-6">
      {/* Activity row */}
      <section>
        <h2 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-3">
          Activity
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <MetricCard
            label="Jobs scraped"
            value={weekScraped}
            hint="this week"
            icon={Briefcase}
            spark={[8, 12, 9, 14, 18, 12, 16]}
          />
          <MetricCard
            label="Applications"
            value={totalApplied}
            hint="all time"
            icon={Send}
            spark={[1, 2, 1, 3, 4, 3, 5]}
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
            value={3}
            hint="LinkedIn accepted"
            icon={Users}
            spark={[0, 1, 1, 2, 2, 3, 3]}
          />
          <MetricCard
            label="API cost"
            value={formatEur(m.api_cost_eur.month)}
            hint={`today ${formatEur(m.api_cost_eur.today)}`}
            icon={CircleDollarSign}
            spark={[0.1, 0.3, 0.2, 0.5, 0.4, 0.6, 0.42]}
            positiveIsGood={false}
          />
        </div>
      </section>

      <section>
        <h2 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-3">
          Distribution
        </h2>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <JobsPerDayChart data={mockJobsPerDay} />
          <AppsBySourceChart data={mockAppsBySource} />
          <PipelinePieChart data={pipelineDist} />
          <TopCompaniesChart data={topCompanies} />
        </div>
      </section>

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
                data={mockApiCostsPerDay}
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
    </div>
  );
}
