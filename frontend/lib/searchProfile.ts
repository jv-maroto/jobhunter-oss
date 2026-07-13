// Cliente del perfil de búsqueda (Pilar 2).
import { api } from "@/lib/api";

export interface PlatformInfo {
  id: string;
  label: string;
  method: string;
  countries: string[];
  apply_support: string;
  tos_risk: string;
  enabled_by_default: boolean;
  /** ¿Existe un scraper de verdad? Si es false, activarla no buscaría nada. */
  implemented: boolean;
  /** "available" | "planned" (declarada, sin scraper) | "apply_only" */
  status: "available" | "planned" | "apply_only" | string;
  /** Clave de entorno necesaria (p.ej. adzuna_app_id). */
  requires_env: string | null;
  notes: string | null;
}

export interface SearchProfile {
  search_preferences: Record<string, unknown> & {
    platforms?: Record<string, boolean>;
    region_preset?: string;
    regions?: string[];
    queries_auto?: boolean;
    queries?: string[];
  };
  regions: string[];
  queries_preview: string[];
  active_platforms: PlatformInfo[];
  suggested_platforms: PlatformInfo[];
}

export interface SearchProfilePatch {
  region_preset?: string;
  regions?: string[];
  platforms?: Record<string, boolean>;
  residence_country?: string;
  queries_auto?: boolean;
  queries?: string[];
  results_per_query?: number;
  hours_old?: number;
}

export interface ScrapeResult {
  scraped: number;
  inserted: number;
  duplicates: number;
}

export const searchProfileApi = {
  get: () => api<SearchProfile>("/settings/search-profile"),
  update: (patch: SearchProfilePatch) =>
    api<SearchProfile>("/settings/search-profile", {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  runScrape: () => api<ScrapeResult>("/scrape/run", { method: "POST" }),
};

export const TOS_COLORS: Record<string, string> = {
  low: "text-emerald-400 border-emerald-400/40",
  medium: "text-amber-400 border-amber-400/40",
  high: "text-rose-400 border-rose-400/40",
};
