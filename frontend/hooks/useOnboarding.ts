"use client";

import { useQuery } from "@tanstack/react-query";
import { onboardingApi } from "@/lib/onboarding";

/**
 * Estado de onboarding. Si el backend no responde, asumimos `onboarded: true`
 * para NO bloquear el dashboard con un wizard cuando simplemente no hay backend
 * (modo demo / mocks). El gate solo redirige cuando el backend dice false.
 */
export function useOnboardingStatus() {
  return useQuery({
    queryKey: ["onboarding", "status"],
    queryFn: async () => {
      try {
        return await onboardingApi.status();
      } catch {
        return { onboarded: true };
      }
    },
    staleTime: 5 * 60_000,
    retry: false,
  });
}
