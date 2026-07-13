"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApiCosts, ApiCostBreakdown, AiProvider } from "@/lib/types";

/** Shape served by the backend at GET /metrics/api-costs */
interface BackendApiCostsResponse {
  since: string;
  until: string;
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cached_input_tokens: number;
  total_cost_eur: number;
  by_provider: Array<{
    bucket: string;
    key: string;
    calls: number;
    input_tokens: number;
    output_tokens: number;
    cached_input_tokens: number;
    cost_eur: number;
  }>;
  by_tier: Array<{
    bucket: string;
    key: string;
    calls: number;
    cost_eur: number;
  }>;
  by_day: Array<{
    bucket: string;
    key: string;
    calls: number;
    cost_eur: number;
  }>;
}

function isoStartOfToday(): string {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

function isoStartOfMonth(): string {
  const d = new Date();
  d.setDate(1);
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

/** Combine two ranges (today + month) into the shape the frontend expects. */
function adapt(
  todayResp: BackendApiCostsResponse,
  monthResp: BackendApiCostsResponse,
): ApiCosts {
  const providersMap = new Map<string, ApiCostBreakdown>();

  for (const row of todayResp.by_provider) {
    providersMap.set(row.key, {
      provider: (row.key as AiProvider) ?? "anthropic",
      calls_today: row.calls,
      calls_month: 0,
      cost_today_eur: row.cost_eur,
      cost_month_eur: 0,
      avg_latency_ms: 0,
    });
  }
  for (const row of monthResp.by_provider) {
    const existing = providersMap.get(row.key);
    if (existing) {
      existing.calls_month = row.calls;
      existing.cost_month_eur = row.cost_eur;
    } else {
      providersMap.set(row.key, {
        provider: (row.key as AiProvider) ?? "anthropic",
        calls_today: 0,
        calls_month: row.calls,
        cost_today_eur: 0,
        cost_month_eur: row.cost_eur,
        avg_latency_ms: 0,
      });
    }
  }

  const daily = (monthResp.by_day ?? []).map((row) => {
    const d = new Date(row.key);
    const label = Number.isNaN(d.getTime())
      ? row.key
      : d.toLocaleDateString("es-ES", { day: "2-digit", month: "short" });
    return { d: label, v: Number(row.cost_eur.toFixed(4)) };
  });

  return {
    total_today_eur: todayResp.total_cost_eur ?? 0,
    total_month_eur: monthResp.total_cost_eur ?? 0,
    by_provider: Array.from(providersMap.values()),
    recent_calls: [],
    daily,
  };
}

export function useApiCosts() {
  return useQuery<ApiCosts>({
    queryKey: ["api-costs"],
    queryFn: async () => {
      // Sin fallback a costes inventados: si el backend falla, que se vea.
      const [today, month] = await Promise.all([
        api<BackendApiCostsResponse>(
          `/metrics/api-costs?since=${encodeURIComponent(isoStartOfToday())}`,
        ),
        api<BackendApiCostsResponse>(
          `/metrics/api-costs?since=${encodeURIComponent(isoStartOfMonth())}`,
        ),
      ]);
      return adapt(today, month);
    },
    staleTime: 30_000,
  });
}
