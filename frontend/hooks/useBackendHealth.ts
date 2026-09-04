"use client";

/**
 * useBackendHealth — reads /health and exposes capabilities + warnings.
 *
 * Separate from useBackendStatus so we don't disturb the Sidebar/TopBar
 * indicators. This is consumed by the yellow banner in AppChrome that tells
 * the user their setup is missing something before they hit an error at
 * "Prepare application" time.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface BackendHealth {
  status: string;
  capabilities?: { typst?: boolean };
  warnings?: string[];
}

export function useBackendHealth() {
  return useQuery<BackendHealth>({
    queryKey: ["backend-health"],
    queryFn: () => api<BackendHealth>("/health"),
    refetchInterval: 60_000,
    staleTime: 30_000,
    // Fail silently — the Sidebar's connection indicator already covers
    // the case where the backend is unreachable.
    retry: 1,
  });
}
