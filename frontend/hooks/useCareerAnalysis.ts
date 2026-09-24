"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface CareerEvidence {
  id: string;
  source: string;
  path: string;
  kind: string;
  value: string;
}

export interface CareerRole {
  title: string;
  fit: "direct" | "adjacent" | "exploratory";
  reason: string;
  evidence_ids: string[];
  gaps: string[];
}

export interface CareerAnalysis {
  id: number;
  source_hash: string;
  status: "queued" | "running" | "completed" | "failed" | "interrupted";
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  result: {
    method: "llm" | "baseline";
    summary: string;
    roles: CareerRole[];
    evidence: CareerEvidence[];
    limitations: string[];
    conflicts: { path: string; variants: unknown; reason: string }[];
  } | null;
}

export interface LatestCareerAnalysis {
  analysis: CareerAnalysis | null;
  last_completed: CareerAnalysis | null;
  current_source_hash: string;
  stale: boolean;
}

export function useCareerAnalysis() {
  return useQuery({
    queryKey: ["career-analysis"],
    queryFn: () => api<LatestCareerAnalysis>("/career/analyses/latest"),
    refetchInterval: (query) => ["queued", "running"].includes(query.state.data?.analysis?.status ?? "") ? 2000 : 15000,
    throwOnError: false,
  });
}

export function useStartCareerAnalysis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ analysis: CareerAnalysis; reused: boolean }>("/career/analyses", {
      method: "POST",
      body: JSON.stringify({}),
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["career-analysis"] }),
    onError: () => qc.invalidateQueries({ queryKey: ["career-analysis"] }),
  });
}

export interface CareerSources {
  sources: { id: string; url: string; kind: string; status: "ready" | "failed"; content_hash: string | null; fetched_at: string | null; error: string | null; truncated: boolean }[];
  refresh: { status: "idle" | "running" | "completed" | "failed" | "interrupted"; started_at: string | null; finished_at: string | null; error: string | null } | null;
}

export function useCareerSources() {
  return useQuery({
    queryKey: ["career-sources"],
    queryFn: () => api<CareerSources>("/career/sources"),
    refetchInterval: (query) => query.state.data?.refresh?.status === "running" ? 2000 : 15000,
    throwOnError: false,
  });
}

export function useRefreshCareerSources() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ status: string; reused: boolean }>("/career/sources/refresh", { method: "POST", body: JSON.stringify({}) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["career-sources"] }),
  });
}
