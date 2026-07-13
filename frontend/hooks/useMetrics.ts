"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CompanyAggregate, Metrics } from "@/lib/types";

export function useMetricsToday() {
  return useQuery<Metrics>({
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
