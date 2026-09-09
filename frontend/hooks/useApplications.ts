"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApplicationReview, ApplicationsPage } from "@/lib/types";

export function useApplications(query: { limit?: number; offset?: number; due_before?: string } = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) params.set(key, String(value));
  }
  return useQuery<ApplicationsPage>({
    queryKey: ["applications", "list", query],
    queryFn: () => api(`/applications?${params.toString()}`),
    throwOnError: false,
    refetchInterval: 60_000,
  });
}

export function useApplication(id: number) {
  return useQuery<ApplicationReview>({
    queryKey: ["applications", id],
    queryFn: () => api(`/applications/${id}`),
    throwOnError: false,
    enabled: Number.isSafeInteger(id) && id > 0,
  });
}

export function useApplicationVersions(id: number) {
  return useQuery<ApplicationReview[]>({
    queryKey: ["applications", "versions", id],
    queryFn: () => api(`/applications/${id}/versions`),
    throwOnError: false,
    enabled: Number.isSafeInteger(id) && id > 0,
  });
}

export function useSaveApplicationCover(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cover_letter_content: string) => api<ApplicationReview>(`/applications/${id}/cover`, {
      method: "PATCH",
      body: JSON.stringify({ cover_letter_content }),
    }),
    onSuccess: (review) => {
      queryClient.setQueryData(["applications", id], review);
      queryClient.invalidateQueries({ queryKey: ["applications", "list"] });
      queryClient.invalidateQueries({ queryKey: ["job", review.job.id] });
    },
  });
}
