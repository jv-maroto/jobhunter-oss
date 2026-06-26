"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { JobStatus } from "@/lib/types";

// Coherent neon-controlled palette
const CHART_COLORS = [
  "hsl(187 92% 49%)",   // cyan (accent-1)
  "hsl(75 85% 60%)",    // lime (accent-2)
  "hsl(142 71% 45%)",   // green (score-good)
  "hsl(38 95% 55%)",    // amber (score-mid)
  "hsl(351 95% 64%)",   // rose (score-bad)
  "hsl(187 80% 38%)",   // teal
  "hsl(75 70% 42%)",    // dark lime
];

const AXIS = "hsl(220 9% 56%)";
const GRID = "hsl(226 22% 16% / 0.6)";

interface TooltipPayloadItem {
  name?: string | number;
  value?: number | string;
  color?: string;
}

function GlassTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-strong rounded-lg px-3 py-2 text-[11px] shadow-2xl">
      {label !== undefined && (
        <div className="mono text-foreground/90 mb-1">{label}</div>
      )}
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 text-muted-foreground">
          <span
            className="h-2 w-2 rounded-full"
            style={{ background: p.color ?? CHART_COLORS[i] }}
          />
          <span className="capitalize">{String(p.name ?? "")}</span>
          <span className="mono ml-2 text-foreground">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

function ChartHeader({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <CardHeader>
      <CardTitle>{title}</CardTitle>
      {description && (
        <p className="text-[11px] text-muted-foreground">{description}</p>
      )}
    </CardHeader>
  );
}

/** Skip rendering Recharts during SSR/static prerender to avoid 0×0 warnings. */
function ClientChart({
  children,
  fallbackHeight = 240,
}: {
  children: React.ReactNode;
  fallbackHeight?: number;
}) {
  const mounted = React.useSyncExternalStore(
    React.useCallback(() => () => {}, []),
    () => true,
    () => false,
  );
  if (!mounted) {
    return (
      <div
        style={{ height: fallbackHeight }}
        className="w-full shimmer rounded-md"
      />
    );
  }
  return <>{children}</>;
}

export function JobsPerDayChart({
  data,
}: {
  data: { date: string; detected: number; high_match: number }[];
}) {
  return (
    <Card variant="glass">
      <ChartHeader
        title="Jobs detected"
        description="Last 30 days — total vs high match (≥70)"
      />
      <CardContent className="h-60">
        <ClientChart><ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id="g-detected" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CHART_COLORS[0]} stopOpacity={0.45} />
                <stop offset="100%" stopColor={CHART_COLORS[0]} stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="g-high" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CHART_COLORS[1]} stopOpacity={0.4} />
                <stop offset="100%" stopColor={CHART_COLORS[1]} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="2 4" stroke={GRID} vertical={false} />
            <XAxis dataKey="date" stroke={AXIS} fontSize={10} tickLine={false} axisLine={false} />
            <YAxis stroke={AXIS} fontSize={10} tickLine={false} axisLine={false} />
            <Tooltip content={<GlassTooltip />} cursor={{ stroke: CHART_COLORS[0], strokeWidth: 1, strokeOpacity: 0.3 }} />
            <Area
              type="monotone"
              dataKey="detected"
              stroke={CHART_COLORS[0]}
              strokeWidth={2}
              fill="url(#g-detected)"
              isAnimationActive
            />
            <Area
              type="monotone"
              dataKey="high_match"
              stroke={CHART_COLORS[1]}
              strokeWidth={2}
              fill="url(#g-high)"
              isAnimationActive
            />
          </AreaChart>
        </ResponsiveContainer></ClientChart>
      </CardContent>
    </Card>
  );
}

export function AppsBySourceChart({
  data,
}: {
  data: { source: string; count: number }[];
}) {
  return (
    <Card variant="glass">
      <ChartHeader title="Applications by source" />
      <CardContent className="h-60">
        <ClientChart><ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="2 4" stroke={GRID} vertical={false} />
            <XAxis dataKey="source" stroke={AXIS} fontSize={10} tickLine={false} axisLine={false} />
            <YAxis stroke={AXIS} fontSize={10} tickLine={false} axisLine={false} />
            <Tooltip content={<GlassTooltip />} cursor={{ fill: "hsl(var(--accent-1) / 0.06)" }} />
            <Bar dataKey="count" radius={[6, 6, 0, 0]} isAnimationActive>
              {data.map((_, i) => (
                <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer></ClientChart>
      </CardContent>
    </Card>
  );
}

export function PipelinePieChart({
  data,
}: {
  data: { name: JobStatus; value: number }[];
}) {
  return (
    <Card variant="glass">
      <ChartHeader title="Pipeline distribution" />
      <CardContent className="h-60">
        <ClientChart><ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              outerRadius={88}
              innerRadius={52}
              paddingAngle={3}
              stroke="hsl(var(--background))"
              strokeWidth={2}
              isAnimationActive
            >
              {data.map((_, i) => (
                <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip content={<GlassTooltip />} />
            <Legend
              verticalAlign="bottom"
              height={32}
              iconType="circle"
              iconSize={8}
              formatter={(v) => (
                <span className="text-[10px] capitalize text-muted-foreground">{v}</span>
              )}
            />
          </PieChart>
        </ResponsiveContainer></ClientChart>
      </CardContent>
    </Card>
  );
}

export function TopCompaniesChart({
  data,
}: {
  data: { company: string; avg_score: number }[];
}) {
  return (
    <Card variant="glass">
      <ChartHeader title="Top companies by avg score" />
      <CardContent className="h-72">
        <ClientChart><ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 16, left: 4, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="2 4" stroke={GRID} horizontal={false} />
            <XAxis type="number" stroke={AXIS} fontSize={10} tickLine={false} axisLine={false} domain={[0, 100]} />
            <YAxis
              type="category"
              dataKey="company"
              stroke={AXIS}
              fontSize={10}
              width={140}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<GlassTooltip />} cursor={{ fill: "hsl(var(--accent-1) / 0.06)" }} />
            <Bar dataKey="avg_score" radius={[0, 6, 6, 0]} isAnimationActive>
              {data.map((d, i) => {
                const score = d.avg_score;
                const color =
                  score >= 70
                    ? CHART_COLORS[2]
                    : score >= 50
                      ? CHART_COLORS[3]
                      : CHART_COLORS[4];
                return <Cell key={i} fill={color} />;
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer></ClientChart>
      </CardContent>
    </Card>
  );
}

export function ApiCostByProviderChart({
  data,
}: {
  data: { provider: string; cost_today_eur: number; cost_month_eur: number }[];
}) {
  return (
    <Card variant="glass">
      <ChartHeader title="API cost by provider" description="Today vs month so far (€)" />
      <CardContent className="h-60">
        <ClientChart><ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="2 4" stroke={GRID} vertical={false} />
            <XAxis dataKey="provider" stroke={AXIS} fontSize={10} tickLine={false} axisLine={false} />
            <YAxis stroke={AXIS} fontSize={10} tickLine={false} axisLine={false} />
            <Tooltip content={<GlassTooltip />} cursor={{ fill: "hsl(var(--accent-1) / 0.06)" }} />
            <Legend
              iconType="circle"
              iconSize={8}
              formatter={(v) => (
                <span className="text-[10px] text-muted-foreground">{v}</span>
              )}
            />
            <Bar dataKey="cost_today_eur" name="today" radius={[6, 6, 0, 0]} fill={CHART_COLORS[0]} />
            <Bar dataKey="cost_month_eur" name="month" radius={[6, 6, 0, 0]} fill={CHART_COLORS[1]} />
          </BarChart>
        </ResponsiveContainer></ClientChart>
      </CardContent>
    </Card>
  );
}

export function ApiCostSparkline({
  data,
  label,
}: {
  data: { d: string; v: number }[];
  label: string;
}) {
  return (
    <Card variant="glass" className="p-4">
      <div className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground mb-2">
        {label}
      </div>
      <div className="h-24">
        <ClientChart><ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
            <Tooltip content={<GlassTooltip />} />
            <Line
              type="monotone"
              dataKey="v"
              stroke={CHART_COLORS[0]}
              strokeWidth={2}
              dot={false}
              isAnimationActive
            />
          </LineChart>
        </ResponsiveContainer></ClientChart>
      </div>
    </Card>
  );
}
