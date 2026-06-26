"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiOrMock } from "@/lib/api";
import type { Person, PersonStatus } from "@/lib/types";

type PersonsResponse = Person[] | { items: Person[]; total?: number };

export function usePersons(status?: PersonStatus) {
  return useQuery<Person[]>({
    queryKey: ["persons", status ?? "all"],
    queryFn: async () => {
      const resp = await apiOrMock<PersonsResponse>(
        `/persons${status ? `?status=${status}` : ""}`,
        "persons",
      );
      if (Array.isArray(resp)) return resp;
      return resp?.items ?? [];
    },
  });
}

export function useMarkPersonSent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      try {
        return await api(`/persons/${id}/mark-sent`, { method: "POST" });
      } catch {
        return { ok: true };
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["persons"] });
    },
  });
}
