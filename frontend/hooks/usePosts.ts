"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiOrMock } from "@/lib/api";
import type { Post } from "@/lib/types";

type PostsResponse = Post[] | { items: Post[]; total?: number };

export function usePosts() {
  return useQuery<Post[]>({
    queryKey: ["posts"],
    queryFn: async () => {
      const resp = await apiOrMock<PostsResponse>("/posts", "posts");
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
