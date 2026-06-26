"use client";

import { useQuery } from "@tanstack/react-query";
import { apiOrMock } from "@/lib/api";
import type { CompanyAggregate, Metrics } from "@/lib/types";

export function useMetricsToday() {
  return useQuery<Metrics>({
    queryKey: ["metrics", "today"],
    queryFn: () => apiOrMock<Metrics>("/metrics/today", "metrics"),
  });
}

export function usePipeline() {
  return useQuery<Metrics["pipeline"]>({
    queryKey: ["pipeline"],
    queryFn: async () => {
      const m = await apiOrMock<Metrics>("/metrics/pipeline", "metrics");
      return m.pipeline;
    },
  });
}

type CompaniesResponse =
  | CompanyAggregate[]
  | { companies: CompanyAggregate[]; total?: number };

export function useCompanies() {
  return useQuery<CompanyAggregate[]>({
    queryKey: ["companies"],
    queryFn: async () => {
      const resp = await apiOrMock<CompaniesResponse>(
        "/metrics/companies",
        "companies",
      );
      if (Array.isArray(resp)) return resp;
      return resp?.companies ?? [];
    },
  });
}
