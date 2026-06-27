"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  createPerson,
  fetchPeople,
  fetchSuggestions,
  type CreatePersonInput,
  type SuggestionsResponse,
} from "@/lib/networking";
import type { Person } from "@/lib/types";

export function useNetworkingSuggestions(opts?: { ai?: boolean; limit?: number }) {
  return useQuery<SuggestionsResponse>({
    queryKey: ["networking", "suggestions", opts?.ai ?? true, opts?.limit ?? null],
    queryFn: async () => {
      try {
        return await fetchSuggestions(opts);
      } catch {
        return {
          suggestions: [],
          skills_used: [],
          companies_used: [],
          ai_used: false,
        } satisfies SuggestionsResponse;
      }
    },
  });
}

export function useNetworkingPeople() {
  return useQuery<Person[]>({
    queryKey: ["networking", "people"],
    queryFn: async () => {
      try {
        return await fetchPeople();
      } catch {
        return [];
      }
    },
  });
}

export function useCreateNetworkingPerson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreatePersonInput) => createPerson(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["networking", "people"] });
      qc.invalidateQueries({ queryKey: ["networking", "suggestions"] });
      qc.invalidateQueries({ queryKey: ["persons"] });
    },
  });
}
