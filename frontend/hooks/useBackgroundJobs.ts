"use client";

/**
 * useBackgroundJobs — aggregated view of every long-running task in the
 * backend so the TopBar can show ONE indicator for the whole app.
 *
 * Polls the individual status endpoints, translates them into a common
 * shape and returns only the ones currently running. Slow polling when
 * idle (30s), fast polling when at least one job is running (3s).
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useScrapeStatus } from "./useScrapeStatus";

export type ActiveJob = {
  key: "scrape" | "trending" | "week";
  label: string;
  progress?: string;
  href?: string;
};

type TrendingStatus = {
  running: boolean;
  requested?: number;
  stories_found?: number;
  created?: number;
  images_done?: number;
  error?: string | null;
};

function useTrendingStatus() {
  return useQuery<TrendingStatus>({
    throwOnError: false,
    queryKey: ["trending-status"],
    queryFn: () => api<TrendingStatus>("/posts/generate-trending-status"),
    refetchInterval: (q) =>
      (q.state.data as TrendingStatus | undefined)?.running ? 3000 : 30000,
    refetchIntervalInBackground: true,
    staleTime: 0,
  });
}

function useWeekStatus() {
  return useQuery<TrendingStatus>({
    throwOnError: false,
    queryKey: ["week-status"],
    queryFn: () => api<TrendingStatus>("/posts/generate-week-status"),
    refetchInterval: (q) =>
      (q.state.data as TrendingStatus | undefined)?.running ? 3000 : 30000,
    refetchIntervalInBackground: true,
    staleTime: 0,
  });
}

export function useBackgroundJobs(): ActiveJob[] {
  const scrape = useScrapeStatus();
  const trending = useTrendingStatus();
  const week = useWeekStatus();

  const jobs: ActiveJob[] = [];

  if (scrape.running) {
    const inserted = scrape.inserted;
    const scraped = scrape.scraped;
    jobs.push({
      key: "scrape",
      label: "Scrapeando ofertas",
      progress:
        scraped > 0
          ? `${scraped} candidatas · ${inserted} nuevas`
          : "Buscando fuentes…",
      href: "/jobs",
    });
  }

  const t = trending.data;
  if (t?.running) {
    const found = t.stories_found ?? 0;
    const created = t.created ?? 0;
    const imgs = t.images_done ?? 0;
    const req = t.requested ?? 0;
    let progress = "Descargando historias…";
    if (created > 0 || imgs > 0) {
      progress = `${created}/${req || found} posts · ${imgs} imgs`;
    } else if (found > 0) {
      progress = `${found} historias · escribiendo con Claude…`;
    }
    jobs.push({
      key: "trending",
      label: "Generando noticias",
      progress,
      href: "/linkedin",
    });
  }

  const w = week.data;
  if (w?.running) {
    const created = w.created ?? 0;
    const req = w.requested ?? 0;
    const imgs = w.images_done ?? 0;
    jobs.push({
      key: "week",
      label: "Generando devlog",
      progress: `${created}/${req} posts · ${imgs} imgs`,
      href: "/linkedin",
    });
  }

  return jobs;
}
