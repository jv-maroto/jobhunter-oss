"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface CommentSuggestion {
  id: number;
  post_url: string;
  author_name?: string | null;
  author_headline?: string | null;
  content_excerpt?: string | null;
  suggested_comment?: string | null;
  relevance_score: number;
  language?: string | null;
  status: string;
  captured_at: string;
}

export function useCommentSuggestions(limit = 10) {
  return useQuery<CommentSuggestion[]>({
    queryKey: ["comments", "suggestions", limit],
    queryFn: async () => {
      try {
        return await api<CommentSuggestion[]>(
          `/comments/suggestions?limit=${limit}`,
        );
      } catch {
        return [];
      }
    },
    staleTime: 60_000,
  });
}

export function useRegenerateComment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      return await api<CommentSuggestion>(`/comments/regenerate/${id}`, {
        method: "POST",
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["comments"] }),
  });
}

export function useMarkCommented() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      return await api<CommentSuggestion>(`/comments/mark-commented/${id}`, {
        method: "POST",
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["comments"] }),
  });
}

export function useSkipComment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      return await api<CommentSuggestion>(`/comments/skip/${id}`, {
        method: "POST",
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["comments"] }),
  });
}

export interface ManualPostIn {
  post_url: string;
  author_name?: string;
  author_headline?: string;
  content_excerpt: string;
  language?: string;
}

export function useAddManualPost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ManualPostIn) => {
      return await api<CommentSuggestion>(`/comments/manual-post`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["comments"] }),
  });
}
