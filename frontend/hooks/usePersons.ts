"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Person, PersonStatus } from "@/lib/types";

type PersonsResponse = Person[] | { items: Person[]; total?: number };

export function usePersons(status?: PersonStatus) {
  return useQuery<Person[]>({
    queryKey: ["persons", status ?? "all"],
    queryFn: async () => {
      const resp = await api<PersonsResponse>(
        `/persons${status ? `?status=${status}` : ""}`,
      );
      if (Array.isArray(resp)) return resp;
      return resp?.items ?? [];
    },
  });
}

export function useMarkPersonSent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      api(`/persons/${id}/mark-sent`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["persons"] });
    },
  });
}
