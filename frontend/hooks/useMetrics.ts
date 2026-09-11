"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CompanyAggregate, Metrics } from "@/lib/types";

export function useMetricsToday() {
  return useQuery<Metrics>({
    throwOnError: false,
    queryKey: ["metrics", "today"],
    queryFn: () => api<Metrics>("/metrics/today"),
  });
}

export function usePipeline() {
  return useQuery<Metrics["pipeline"]>({
    queryKey: ["pipeline"],
    queryFn: async () => {
      const m = await api<Metrics>("/metrics/pipeline");
      return m.pipeline;
    },
    // Pipeline numbers don't change per second — cache 60s and keep in
    // memory 30 min so returning to /pipeline is instant.
    staleTime: 60_000,
    gcTime: 30 * 60_000,
  });
}

type CompaniesResponse =
  | CompanyAggregate[]
  | { companies: CompanyAggregate[]; total?: number };

export function useCompanies() {
  return useQuery<CompanyAggregate[]>({
    queryKey: ["companies"],
    queryFn: async () => {
      const resp = await api<CompaniesResponse>("/metrics/companies");
      if (Array.isArray(resp)) return resp;
      return resp?.companies ?? [];
    },
  });
}
