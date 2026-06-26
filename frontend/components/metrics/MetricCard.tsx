"use client";

import * as React from "react";
import type { LucideIcon } from "lucide-react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Line, LineChart, ResponsiveContainer } from "recharts";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

function useMounted() {
  return React.useSyncExternalStore(
    React.useCallback(() => () => {}, []),
    () => true,
    () => false,
  );
}

export interface MetricCardProps {
  label: string;
  value: string | number;
  hint?: string;
  icon?: LucideIcon;
  /** Percentage delta vs previous period. Positive = up. */
  delta?: number;
  /** Whether positive delta is good (default true). */
  positiveIsGood?: boolean;
  /** Sparkline data points. */
  spark?: number[];
  accent?: "default" | "warn" | "good";
}

export function MetricCard({
  label,
  value,
  hint,
  icon: Icon,
  delta,
  positiveIsGood = true,
  spark,
  accent = "default",
}: MetricCardProps) {
  const accentColor =
    accent === "warn"
      ? "hsl(var(--accent-warn))"
      : accent === "good"
        ? "hsl(var(--score-good))"
        : "hsl(var(--accent-1))";

  const deltaGood = delta === undefined
    ? null
    : positiveIsGood
      ? delta >= 0
      : delta <= 0;

  const mounted = useMounted();

  return (
    <Card variant="glass" hover="lift" className="p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            {Icon && <Icon className="h-3 w-3" />}
            {label}
          </div>
          <div
            className="mt-2 mono text-2xl font-semibold tabular-nums leading-none"
            style={{ color: "hsl(var(--foreground))" }}
          >
            {value}
          </div>
          <div className="mt-1.5 flex items-center gap-2 text-[10px] text-muted-foreground">
            {delta !== undefined && (
              <span
                className={cn(
                  "inline-flex items-center gap-0.5 mono font-medium",
                  deltaGood
                    ? "text-[hsl(var(--score-good))]"
                    : "text-[hsl(var(--accent-warn))]",
                )}
              >
                {delta >= 0 ? (
                  <ArrowUp className="h-2.5 w-2.5" />
                ) : (
                  <ArrowDown className="h-2.5 w-2.5" />
                )}
                {Math.abs(delta).toFixed(1)}%
              </span>
            )}
            {hint && <span className="truncate">{hint}</span>}
          </div>
        </div>

        {spark && spark.length > 1 && mounted && (
          <div className="h-12 w-20 shrink-0 -mr-1 -mt-1">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={spark.map((v, i) => ({ i, v }))}>
                <Line
                  type="monotone"
                  dataKey="v"
                  stroke={accentColor}
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </Card>
  );
}
