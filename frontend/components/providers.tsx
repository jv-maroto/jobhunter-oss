"use client";

import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import { CommandPalette } from "@/components/layout/CommandPalette";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
    >
      <QueryClientProvider client={client}>
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
      </QueryClientProvider>
    </ThemeProvider>
  );
}
