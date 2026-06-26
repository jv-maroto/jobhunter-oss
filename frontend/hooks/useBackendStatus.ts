"use client";

import { useQuery } from "@tanstack/react-query";
import { ping } from "@/lib/api";

export function useBackendStatus() {
  return useQuery({
    queryKey: ["backend-status"],
    queryFn: ping,
    refetchInterval: 30_000,
    staleTime: 10_000,
  });
}
