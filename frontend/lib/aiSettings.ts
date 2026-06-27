// Cliente de ajustes de IA (router + keystore en data/integrations/ai.json).
// Las claves se envían a PUT y NUNCA se devuelven en claro: solo `has_key`.
import { api } from "@/lib/api";

export type AiMode = "auto" | "cloud" | "local" | "off";
export type AiProvider = "anthropic" | "openai" | "gemini";

export interface AiHasKey {
  anthropic: boolean;
  openai: boolean;
  gemini: boolean;
}

export interface AiSettings {
  ai_mode: AiMode;
  ai_cloud_provider: AiProvider;
  ai_scraping_enabled: boolean;
  has_key: AiHasKey;
  local_available: boolean;
  active: string;
}

export interface AiSettingsPatch {
  ai_mode?: AiMode;
  ai_cloud_provider?: AiProvider;
  ai_scraping_enabled?: boolean;
  keys?: Partial<Record<AiProvider, string>>;
}

export interface AiTestResult {
  ok: boolean;
  provider: string;
  error?: string;
}

export const AI_PROVIDERS: { id: AiProvider; label: string; keyPlaceholder: string }[] = [
  { id: "anthropic", label: "Anthropic (Claude)", keyPlaceholder: "sk-ant-…" },
  { id: "openai", label: "OpenAI (GPT)", keyPlaceholder: "sk-…" },
  { id: "gemini", label: "Google Gemini", keyPlaceholder: "AIza…" },
];

export const aiSettingsApi = {
  get: () => api<AiSettings>("/settings/ai"),
  update: (patch: AiSettingsPatch) =>
    api<AiSettings>("/settings/ai", {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  test: () => api<AiTestResult>("/settings/ai/test", { method: "POST" }),
};
