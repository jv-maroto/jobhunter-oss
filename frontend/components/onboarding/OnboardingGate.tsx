"use client";

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";
import { useOnboardingStatus } from "@/hooks/useOnboarding";

/**
 * Si la instancia aún no ha completado el onboarding (backend dice
 * `onboarded:false`), redirige a `/onboarding`. El propio wizard se monta como
 * overlay full-screen, así que tapa el dashboard mientras se completa.
 *
 * Se monta dentro de <Providers> en el layout raíz. No renderiza nada visible.
 */
export function OnboardingGate() {
  const { data } = useOnboardingStatus();
  const pathname = usePathname();
  const router = useRouter();

  React.useEffect(() => {
    if (data && data.onboarded === false && pathname !== "/onboarding") {
      router.replace("/onboarding");
    }
  }, [data, pathname, router]);

  return null;
}
