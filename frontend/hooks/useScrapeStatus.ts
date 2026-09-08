"use client";

/**
 * useScrapeStatus — single source of truth for /jobs/scrape-status.
 *
 * Backed by TanStack Query so:
 *   - Multiple tabs/pages sharing the same query key see the same state
 *   - Poll continues while the tab is in the background (refetchIntervalInBackground)
 *   - Coming back after minimising the window doesn't reset "running=false"
 *     — the next poll picks up whatever the backend is actually doing
 *
 * Fires success/error toasts once per running→stopped transition.
 */

import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";

export interface ScrapeStatus {
  running: boolean;
  started_at: string | null;
  finished_at: string | null;
  scraped: number;
  inserted: number;
  duplicates: number;
  error: string | null;
}

export function useScrapeStatus() {
  const qc = useQueryClient();
  const prevRunningRef = React.useRef<boolean | null>(null);

  const query = useQuery<ScrapeStatus>({
    queryKey: ["scrape-status"],
    queryFn: () => api<ScrapeStatus>("/jobs/scrape-status"),
    // Poll while running; slower poll when idle to catch scrapes started from
    // another tab / the scheduler / the extension.
    refetchInterval: (q) =>
      (q.state.data as ScrapeStatus | undefined)?.running ? 4000 : 30000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    staleTime: 0,
  });

  // Emit a single toast on the running=true → running=false edge, and
  // debounce cache invalidation. Before the debounce, finishing a scrape
  // fired 3 immediate invalidateQueries → 3 network refetches in the same
  // tick, each pulling 300+ rows. On a busy scheduler run the UI froze for
  // ~10s. 300ms is invisible to the user but coalesces the burst.
  const invalidateTimerRef = React.useRef<number | null>(null);
  React.useEffect(() => {
    const s = query.data;
    if (!s) return;
    const prev = prevRunningRef.current;
    if (prev === true && s.running === false) {
      if (s.error) {
        toast.error("Scrape falló", { description: s.error.slice(0, 200) });
      } else {
        toast.success(
          `Scrape OK · ${s.scraped} found · ${s.inserted} new`,
          {
            description:
              s.duplicates > 0
                ? `${s.duplicates} duplicados ignorados.`
                : undefined,
            duration: 6000,
          },
        );
      }
      if (invalidateTimerRef.current !== null) {
        window.clearTimeout(invalidateTimerRef.current);
      }
      invalidateTimerRef.current = window.setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["jobs"] });
        qc.invalidateQueries({ queryKey: ["pipeline"] });
        qc.invalidateQueries({ queryKey: ["metrics"] });
        invalidateTimerRef.current = null;
      }, 300);
    }
    prevRunningRef.current = s.running;
  }, [query.data, qc]);

  React.useEffect(() => {
    // Cleanup pending timer on unmount to avoid a stray refetch on a page
    // the user has already left.
    return () => {
      if (invalidateTimerRef.current !== null) {
        window.clearTimeout(invalidateTimerRef.current);
      }
    };
  }, []);

  return {
    ...query,
    running: query.data?.running ?? false,
    scraped: query.data?.scraped ?? 0,
    inserted: query.data?.inserted ?? 0,
    duplicates: query.data?.duplicates ?? 0,
    startedAt: query.data?.started_at,
  };
}
