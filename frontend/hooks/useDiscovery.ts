"use client";

import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface DiscoveryStatus {
  running: boolean; phase: string; started_at: string | null; finished_at: string | null;
  scraped: number; inserted: number; duplicates: number; completed_sources: number;
  total_sources: number; error: string | null; queries?: string[]; countries?: string[];
}

export function useDiscovery() {
  const cache = useQueryClient();
  const previous = useRef("");
  const query = useQuery({
    queryKey: ["discovery-status"],
    queryFn: () => api<DiscoveryStatus>("/jobs/discover-status"),
    refetchInterval: (q) => q.state.data?.running ? 2500 : 30000,
    refetchIntervalInBackground: true,
    throwOnError: false,
  });
  useEffect(() => {
    if (!query.data) return;
    const marker = `${query.data.started_at}:${query.data.inserted}:${query.data.completed_sources}:${query.data.running}`;
    if (previous.current && marker !== previous.current) {
      cache.invalidateQueries({ queryKey: ["jobs"] });
      cache.invalidateQueries({ queryKey: ["metrics"] });
    }
    previous.current = marker;
  }, [query.data, cache]);
  return query;
}
