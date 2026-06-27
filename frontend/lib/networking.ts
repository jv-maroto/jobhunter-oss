// Cliente HTTP para la pagina Networking (sustituye LinkedIn).
import { api } from "@/lib/api";
import type { Person } from "@/lib/types";

export interface NetworkingSuggestion {
  full_name?: string | null;
  headline: string;
  company?: string | null;
  reason: string;
  priority: number;
  kind: "person" | "archetype";
  skill_match: string[];
}

export interface SuggestionsResponse {
  suggestions: NetworkingSuggestion[];
  skills_used: string[];
  companies_used: string[];
  ai_used: boolean;
}

export interface CreatePersonInput {
  full_name: string;
  headline?: string;
  company?: string;
  profile_url?: string;
}

export async function fetchSuggestions(opts?: {
  ai?: boolean;
  limit?: number;
}): Promise<SuggestionsResponse> {
  const sp = new URLSearchParams();
  if (opts?.ai === false) sp.set("ai", "false");
  if (typeof opts?.limit === "number") sp.set("limit", String(opts.limit));
  const qs = sp.toString();
  return api<SuggestionsResponse>(
    `/networking/suggestions${qs ? `?${qs}` : ""}`,
  );
}

export async function fetchPeople(): Promise<Person[]> {
  return api<Person[]>("/networking/people");
}

export async function createPerson(input: CreatePersonInput): Promise<Person> {
  return api<Person>("/networking/people", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
