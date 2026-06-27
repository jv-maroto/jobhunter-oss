// Cliente del onboarding de primer uso (Pilar 1).
import { api, apiUpload } from "@/lib/api";

export type Json = Record<string, unknown>;

export interface Personal {
  name?: string;
  email?: string;
  phone?: string;
  location?: string;
  location_short?: string;
  title?: string;
  github?: string;
  linkedin?: string;
  portfolio?: string;
  [k: string]: unknown;
}

export interface CvMaster {
  personal?: Personal;
  summary_es?: string;
  summary_en?: string;
  experience?: Json[];
  education?: Json[];
  certifications?: Json[];
  languages?: Json[];
  skills?: Record<string, string[]>;
  projects?: Json[];
  search_preferences?: Json;
  [k: string]: unknown;
}

export interface Conflict {
  field: string;
  kept: unknown;
  kept_source?: string;
  other: unknown;
  other_source?: string;
}

export interface MergeResult {
  cv_master: CvMaster;
  field_sources: Record<string, string>;
  conflicts: Conflict[];
  llm_used: boolean;
}

export interface OnboardingStatus {
  onboarded: boolean;
}

export type OnboardingSource = "github" | "linkedin" | "cv";

export interface FragmentResponse {
  ok: boolean;
  fragment: Json;
  warnings?: string[];
  chars?: number;
}

// Rol de trabajo sugerido (IA tier generation o heurística de experiencia+skills).
export interface RoleSuggestion {
  id: string;
  label: string;
  why: string;
}

export const REGION_PRESETS = [
  { id: "only_spain", label: "Solo España", regions: ["ES"] },
  { id: "all_europe", label: "Toda Europa", regions: ["EU"] },
  { id: "remote_worldwide", label: "Remoto (worldwide)", regions: ["REMOTE"] },
] as const;

// Países sueltos para selección "custom".
export const COUNTRY_OPTIONS = [
  { iso: "ES", label: "España" },
  { iso: "DE", label: "Alemania" },
  { iso: "FR", label: "Francia" },
  { iso: "SE", label: "Suecia" },
  { iso: "GB", label: "Reino Unido" },
  { iso: "NL", label: "Países Bajos" },
  { iso: "IT", label: "Italia" },
  { iso: "PT", label: "Portugal" },
  { iso: "REMOTE", label: "Remoto" },
] as const;

export const onboardingApi = {
  status: () => api<OnboardingStatus>("/onboarding/status"),

  github: (username: string) =>
    api<FragmentResponse>("/onboarding/github", {
      method: "POST",
      body: JSON.stringify({ username }),
    }),

  uploadCv: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiUpload<FragmentResponse>("/onboarding/cv", fd);
  },

  uploadLinkedin: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiUpload<FragmentResponse>("/onboarding/linkedin", fd);
  },

  linkedinPaste: (text: string) =>
    api<FragmentResponse>("/onboarding/linkedin/paste", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  merge: () => api<MergeResult>("/onboarding/merge", { method: "POST" }),

  suggestRoles: () =>
    api<{ roles: RoleSuggestion[] }>("/onboarding/roles", { method: "POST" }),

  draft: () => api<{ fragments: Record<string, Json>; merged: MergeResult | null }>(
    "/onboarding/draft",
  ),

  complete: (cv_master: CvMaster) =>
    api<{ ok: boolean; path: string; onboarded: boolean }>("/onboarding/complete", {
      method: "POST",
      body: JSON.stringify({ cv_master }),
    }),

  reset: () => api<{ ok: boolean }>("/onboarding/reset", { method: "POST" }),
};
