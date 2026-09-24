"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Post } from "@/lib/types";

type PostsResponse = Post[] | { items: Post[]; total?: number };

export function usePosts() {
  return useQuery<Post[]>({
    queryKey: ["posts"],
    queryFn: async () => {
      const resp = await api<PostsResponse>("/posts");
      if (Array.isArray(resp)) return resp;
      return resp?.items ?? [];
    },
  });
}

export function useSchedulePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      when,
    }: {
      id: number;
      when?: string | Date;
    }) => {
      const body =
        when !== undefined
          ? JSON.stringify({
              when:
                typeof when === "string" ? when : when.toISOString(),
            })
          : JSON.stringify({});
      return api(`/posts/${id}/schedule`, {
        method: "POST",
        body,
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["posts"] }),
  });
}

export function useMarkPostPublished() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      api<Post>(`/posts/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "published" }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["posts"] }),
  });
}

export interface NewsGeneration {
  running: boolean;
  created: number;
  requested: number;
  images_done: number;
  finished_at: string | null;
  error: string | null;
}

export function useNewsGeneration() {
  return useQuery<NewsGeneration>({
    queryKey: ["news-generation"],
    queryFn: () => api("/posts/generate-trending-status"),
    refetchInterval: (query) => query.state.data?.running ? 2000 : 15000,
    staleTime: 0,
    throwOnError: false,
  });
}

export function useRegenerateNews() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ status: string }>("/posts/generate-trending", {
      method: "POST", body: JSON.stringify({ count: 15, language: "es", replace_drafts: true }),
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["news-generation"] }),
  });
}

export function useDeleteOldNews() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ deleted: number }>("/posts/trending/old?days=7", { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["posts"] }),
  });
}
