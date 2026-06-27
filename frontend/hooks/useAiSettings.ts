"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { aiSettingsApi, type AiSettings, type AiSettingsPatch } from "@/lib/aiSettings";

const AI_KEY = ["settings", "ai"] as const;

export function useAiSettings() {
  return useQuery({
    queryKey: AI_KEY,
    queryFn: () => aiSettingsApi.get(),
    staleTime: 30_000,
  });
}

/**
 * True solo si hay una API de pago (cloud) conectada con clave. Con Ollama local
 * o sin IA es false -> los widgets de coste de API (siempre €0) se ocultan.
 * Mientras carga devuelve `false` para no parpadear coste a 0.
 */
export function useHasPaidApi(): boolean {
  const { data } = useAiSettings();
  const hk = data?.has_key;
  return !!hk && (hk.anthropic || hk.openai || hk.gemini);
}

export function useUpdateAiSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: AiSettingsPatch) => aiSettingsApi.update(patch),
    onSuccess: (data: AiSettings) => {
      // El PUT devuelve el mismo shape que el GET: sembramos e invalidamos.
      qc.setQueryData(AI_KEY, data);
      qc.invalidateQueries({ queryKey: AI_KEY });
    },
  });
}

export function useTestAiSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => aiSettingsApi.test(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: AI_KEY });
    },
  });
}
