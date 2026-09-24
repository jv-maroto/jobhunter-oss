"use client";

import * as React from "react";
import { QueryClient, QueryClientProvider, dehydrate, hydrate } from "@tanstack/react-query";
import { readJobCache, writeJobCache } from "@/lib/jobCache";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { LanguageProvider } from "@/lib/i18n";
import { readStoredPalette } from "@/components/layout/PaletteSwitcher";

/**
 * Restores the persisted accent palette (<html data-palette="…">) as early as
 * possible on the client. Renders nothing. Runs in a layout effect so the
 * attribute is set before paint, minimizing any flash of the default palette.
 */
function PaletteInit() {
  React.useLayoutEffect(() => {
    document.documentElement.dataset.palette = readStoredPalette();
  }, []);
  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 60_000,
            gcTime: 24 * 60 * 60_000,
            refetchOnWindowFocus: false,
            retry: 1,
            // Antes los fallos se tapaban con datos inventados (apiOrMock).
            // Ahora se propagan al error boundary (`app/error.tsx`) para que
            // quede claro que el backend no responde, en vez de enseñar
            // ofertas que no existen.
            throwOnError: (_error, query) => query.state.data === undefined,
          },
        },
      }),
  );

  React.useEffect(() => {
    const maxAge = 24 * 60 * 60_000;
    let disposed = false;
    let restored = false;
    void readJobCache().then((saved) => {
      if (!disposed && saved && Date.now() - saved.savedAt < maxAge) hydrate(client, saved.state);
    }).catch(() => { /* Browser storage may be unavailable. */ }).finally(() => { restored = true; });
    let timer: ReturnType<typeof setTimeout> | undefined;
    const persist = () => {
      if (!restored) return;
      clearTimeout(timer);
      timer = setTimeout(() => {
        try {
          const state = dehydrate(client, {
            shouldDehydrateMutation: () => false,
            shouldDehydrateQuery: (q) => ["jobs", "pipeline", "metrics"].includes(String(q.queryKey[0]))
              && q.state.data !== undefined && !q.state.isInvalidated
              && Date.now() - q.state.dataUpdatedAt < maxAge,
          });
          void writeJobCache({ savedAt: Date.now(), state }).catch(() => {});
        } catch { /* A full cache must never prevent displaying jobs. */ }
      }, 300);
    };
    const unsubscribe = client.getQueryCache().subscribe(persist);
    return () => { disposed = true; unsubscribe(); clearTimeout(timer); };
  }, [client]);

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
    >
      <QueryClientProvider client={client}>
        <LanguageProvider>
          <PaletteInit />
          <div className="cc-backdrop" aria-hidden />
          {children}
          <CommandPalette />
        <Toaster
          position="bottom-right"
          theme="dark"
          richColors
          closeButton
          toastOptions={{
            unstyled: false,
            classNames: {
              toast:
                "!bg-[hsl(var(--surface))]/85 backdrop-blur-xl !border !border-[hsl(var(--border-strong))] !text-foreground !rounded-xl !shadow-2xl",
              title: "!font-medium",
              description: "!text-muted-foreground",
            },
          }}
          />
        </LanguageProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
