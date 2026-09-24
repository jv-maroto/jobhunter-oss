"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api";
import { jobCountries } from "@/lib/jobCountries";
import type {
  Job,
  JobStatus,
  JobTrack,
  PrepareApplicationResponse,
  SalaryBand,
} from "@/lib/types";

export type JobLocationFilter = "all" | "spain" | "spain_remote" | "remote" | "remote_worldwide";

export interface JobsQuery {
  location_filter?: JobLocationFilter;
  country?: string;
  verified_only?: boolean;
  status?: JobStatus;
  min_score?: number;
  source?: string;
  track?: JobTrack;
  limit?: number;
  offset?: number;
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

export function useJobCollection() {
  return useQuery<{ items: Job[]; total: number }>({
    throwOnError: false,
    queryKey: ["jobs", "snapshot"],
    queryFn: ({ signal }) => api("/jobs/snapshot", { signal }),
  });
}

export function matchesJobLocation(job: Job, filter: JobLocationFilter = "all"): boolean {
  const location = (job.location || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const remote = job.remote || /\b(remote|remoto|remota|home[ -]based|work from home)\b/.test(location);
  if (filter === "spain_remote") return Boolean(remote) && matchesJobLocation(job, "spain");
  if (filter === "spain") {
    return !/\bport of spain\b/.test(location) && (
      /\b(spain|espana)\b|(?:^|[,;\s])es(?:$|[,;\s])/.test(location)
      || /^(madrid|barcelona|valencia|sevilla|seville|malaga|bilbao|zaragoza|alicante|murcia|granada|las palmas|santa cruz de tenerife)$/.test(location.trim())
    );
  }
  if (filter === "remote") return Boolean(remote);
  if (filter === "remote_worldwide") return Boolean(remote)
    && /\b(worldwide|world wide|anywhere|any country|todo el mundo|cualquier pais)\b/.test(location)
    && !/\b(only|solo|except|excepto|excluding|restricted|residents?)\b/.test(location);
  return true;
}

// Persisted browser snapshots must age evidence even when the API is offline.
export function currentJobAvailability(job: Job): string {
  const value = job.availability;
  if (!value) return "unverified";
  let deadline = value.expires_at ? Date.parse(value.expires_at) : NaN;
  if (value.expires_at && /^\d{4}-\d{2}-\d{2}$/.test(value.expires_at)) deadline += 86_400_000;
  const now = Date.now();
  if (deadline <= now) return "expired";
  if (value.status === "active") {
    const age = now - Date.parse(value.checked_at);
    if (!Number.isFinite(age) || age < 0 || age > 86_400_000) return "unverified";
  }
  return value.status;
}

function visibleJob(job: Job): boolean {
  if (job.status !== "detected") return true; // Keep application history.
  const status = currentJobAvailability(job);
  if (status === "expired") return false;
  let host = "";
  try { host = new URL(job.source_url).hostname; } catch { /* Missing source. */ }
  const indeed = job.source?.toLowerCase() === "indeed"
    || /(^|\.)indeed\.(com|[a-z]{2}|co\.[a-z]{2}|com\.[a-z]{2})$/.test(host);
  return !indeed || status === "active";
}

function filterJobs(items: Job[], q: JobsQuery) {
  return items.filter((job) =>
    visibleJob(job)
    && (!q.country || (q.country === "unknown" ? jobCountries(job).length === 0 : jobCountries(job).includes(q.country)))
    && matchesJobLocation(job, q.location_filter)
    && (!q.verified_only || currentJobAvailability(job) === "active")
    && (!q.status || job.status === q.status)
    && (!q.source || job.source === q.source)
    && (!q.track || job.track === q.track)
    && job.match_score >= (q.min_score ?? 0));
}

export function useJobsPage(q: JobsQuery) {
  const query = useJobCollection();
  const items = filterJobs(query.data?.items ?? [], q).sort((a, b) => b.match_score - a.match_score);
  const offset = q.offset ?? 0;
  return { ...query, data: query.data ? {
    items: items.slice(offset, offset + (q.limit ?? 100)), total: items.length,
  } : undefined };
}

export function useJobs(q: JobsQuery = {}) {
  const query = useJobCollection();
  const items = filterJobs(query.data?.items ?? [], q);
  const offset = q.offset ?? 0;
  return { ...query, data: query.data ? items.slice(offset, offset + (q.limit ?? 100)) : undefined };
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
        { timeoutMs: 300_000 },
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
