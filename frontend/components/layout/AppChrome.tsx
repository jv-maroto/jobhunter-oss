"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { useOnboardingStatus } from "@/hooks/useOnboarding";

/**
 * Decide si mostrar el chrome (Sidebar + TopBar). Durante el onboarding —o si la
 * instancia aún no está onboarded— se oculta para que el wizard ocupe toda la
 * pantalla sin barra lateral detrás.
 */
export function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data } = useOnboardingStatus();

  const hideChrome = pathname === "/onboarding" || data?.onboarded === false;

  if (hideChrome) {
    return <main className="min-h-screen">{children}</main>;
  }

  return (
    <>
      <Sidebar />
      <div className="relative z-10 flex min-h-screen flex-col md:pl-[76px] min-w-0">
        <TopBar />
        <main className="flex-1 overflow-x-hidden p-5 lg:p-6 min-w-0">{children}</main>
      </div>
    </>
  );
}
