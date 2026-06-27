"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { searchProfileApi, type SearchProfilePatch } from "@/lib/searchProfile";

export function useSearchProfile() {
  return useQuery({
    queryKey: ["search-profile"],
    queryFn: () => searchProfileApi.get(),
    staleTime: 60_000,
  });
}

export function useUpdateSearchProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: SearchProfilePatch) => searchProfileApi.update(patch),
    onSuccess: (data) => {
      qc.setQueryData(["search-profile"], data);
    },
  });
}

export function useRunScrape() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => searchProfileApi.runScrape(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["metrics"] });
    },
  });
}
