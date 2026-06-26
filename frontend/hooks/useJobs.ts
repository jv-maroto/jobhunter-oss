"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api, apiOrMock } from "@/lib/api";
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
}

function buildSearch(q: JobsQuery): string {
  const sp = new URLSearchParams();
  if (q.status) sp.set("status", q.status);
  if (typeof q.min_score === "number")
    sp.set("min_score", String(q.min_score));
  if (q.source) sp.set("source", q.source);
  if (q.track) sp.set("track", q.track);
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export interface SwipeQuery {
  track: JobTrack;
  remote_only?: boolean;
  min_band?: SalaryBand;
}

export function useSwipeJobs(q: SwipeQuery) {
  return useQuery<Job[]>({
    queryKey: ["jobs", "swipe", q],
    queryFn: async () => {
      const sp = new URLSearchParams({ track: q.track });
      if (q.remote_only) sp.set("remote_only", "true");
      if (q.min_band) sp.set("min_band", q.min_band);
      return await api<Job[]>(`/jobs/swipe?${sp.toString()}`);
    },
  });
}

type JobsResponse = Job[] | { items: Job[]; total?: number };

export function useJobs(q: JobsQuery = {}) {
  return useQuery<Job[]>({
    queryKey: ["jobs", q],
    queryFn: async () => {
      const resp = await apiOrMock<JobsResponse>(`/jobs${buildSearch(q)}`, "jobs");
      if (Array.isArray(resp)) return resp;
      return resp?.items ?? [];
    },
  });
}

export function useJob(id: number) {
  return useQuery<Job | undefined>({
    queryKey: ["job", id],
    queryFn: async () => {
      try {
        return await api<Job>(`/jobs/${id}`);
      } catch {
        const { mockJobs } = await import("@/lib/mock");
        return mockJobs.find((j) => j.id === id);
      }
    },
  });
}

export function usePrepareApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (jobId: number) => {
      try {
        return await api<PrepareApplicationResponse>(
          `/jobs/${jobId}/prepare-application`,
          { method: "POST" },
        );
      } catch {
        return {
          cv_path: `/tmp/cv_job_${jobId}.pdf`,
          cover_letter_path: `/tmp/cover_job_${jobId}.pdf`,
          source_url: "",
        } satisfies PrepareApplicationResponse;
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["pipeline"] });
      qc.invalidateQueries({ queryKey: ["metrics"] });
    },
  });
}

export function useUpdateJobStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      status,
      notes,
    }: {
      id: number;
      status: JobStatus;
      notes?: string;
    }) => {
      const body: Record<string, unknown> = { status };
      if (typeof notes === "string") body.notes = notes;
      try {
        return await api<Job>(`/jobs/${id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      } catch {
        return { id, status, notes } as Partial<Job>;
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["pipeline"] });
      qc.invalidateQueries({ queryKey: ["metrics"] });
    },
  });
}
