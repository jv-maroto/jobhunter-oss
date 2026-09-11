"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  Job,
  JobStatus,
  JobTrack,
  PrepareApplicationResponse,
  SalaryBand,
} from "@/lib/types";

export interface JobsQuery {
  status?: JobStatus;
  min_score?: number;
  source?: string;
  track?: JobTrack;
  limit?: number;
  offset?: number;
}

function buildSearch(q: JobsQuery): string {
  const sp = new URLSearchParams();
  if (q.status) sp.set("status", q.status);
  if (typeof q.min_score === "number")
    sp.set("min_score", String(q.min_score));
  if (q.source) sp.set("source", q.source);
  if (q.track) sp.set("track", q.track);
  if (q.limit !== undefined) sp.set("limit", String(q.limit));
  if (q.offset !== undefined) sp.set("offset", String(q.offset));
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export interface SwipeQuery {
  track?: JobTrack;
  remote_only?: boolean;
  min_band?: SalaryBand;
}

export function useSwipeJobs(q: SwipeQuery) {
  return useQuery<Job[]>({
    throwOnError: false,
    queryKey: ["jobs", "swipe", q],
    queryFn: async () => {
      const sp = new URLSearchParams();
      if (q.track) sp.set("track", q.track);
      if (q.remote_only) sp.set("remote_only", "true");
      if (q.min_band) sp.set("min_band", q.min_band);
      return await api<Job[]>(`/jobs/swipe?${sp.toString()}`);
    },
  });
}

type JobsResponse = Job[] | { items: Job[]; total?: number };

export function useJobsPage(q: JobsQuery) {
  return useQuery<{ items: Job[]; total: number }>({
    throwOnError: false,
    queryKey: ["jobs", "page", q],
    queryFn: () => api(`/jobs${buildSearch(q)}`),
    // Keep the previous page visible while a new filter is being fetched —
    // otherwise every slider tick clears the table for ~19s and the user
    // sees "Cargando trabajos" from scratch. With placeholderData the old
    // rows stay on screen with the isFetching chip on top.
    placeholderData: keepPreviousData,
    // /jobs is expensive (backend rescores every row → ~19s per request).
    // 5 min stale + 30 min cache means "salir a /pipeline y volver a /jobs"
    // shows the previous table instantly, revalidating silently only if
    // the user has been away for real time.
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
  });
}

export function useJobs(q: JobsQuery = {}) {
  return useQuery<Job[]>({
    throwOnError: false,
    queryKey: ["jobs", q],
    queryFn: async () => {
      const resp = await api<JobsResponse>(`/jobs${buildSearch(q)}`);
      if (Array.isArray(resp)) return resp;
      return resp?.items ?? [];
    },
  });
}

export function useJob(id: number) {
  return useQuery<Job | undefined>({
    throwOnError: false,
    queryKey: ["job", id],
    enabled: Number.isSafeInteger(id) && id > 0,
    queryFn: async () => {
      return api<Job>(`/jobs/${id}`);
    },
  });
}

export function usePrepareApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (jobId: number) =>
      api<PrepareApplicationResponse>(
        `/jobs/${jobId}/prepare-application`,
        { method: "POST" },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["job"] });
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["pipeline"] });
      qc.invalidateQueries({ queryKey: ["metrics"] });
    },
  });
}

export function useUpdateJobStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: {
      id: number;
      status?: JobStatus;
      notes?: string | null;
      next_action?: string | null;
      next_action_at?: string | null;
      applied_at?: string | null;
      application_id?: number;
    }) => {
      return api<Job>(`/jobs/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["job"] });
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["pipeline"] });
      qc.invalidateQueries({ queryKey: ["metrics"] });
    },
  });
}

export function useDeleteJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      api<{ deleted: boolean; job_id: number; applications: number }>(
        `/jobs/${id}`,
        { method: "DELETE" },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["pipeline"] });
      qc.invalidateQueries({ queryKey: ["metrics"] });
      qc.invalidateQueries({ queryKey: ["applications"] });
    },
  });
}
