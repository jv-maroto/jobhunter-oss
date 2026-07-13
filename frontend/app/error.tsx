"use client"; // Los error boundaries deben ser Client Components

import * as React from "react";
import { AlertTriangle, RefreshCcw, Terminal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BASE_URL } from "@/lib/api";

/**
 * Se muestra cuando una query falla. Sustituye al viejo comportamiento de
 * devolver datos mock: es preferible decir "el backend no responde" a enseñar
 * ofertas de empleo inventadas.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // Un fetch fallido (backend caído) da un TypeError sin `status`.
  const isOffline =
    error.message.includes("fetch") ||
    error.message.includes("Failed") ||
    error.message.includes("NetworkError");

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Card variant="glass" className="max-w-lg w-full">
        <CardHeader>
          <CardTitle className="inline-flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-[hsl(38_95%_55%)]" />
            {isOffline ? "No se puede conectar con el backend" : "Algo ha fallado"}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isOffline ? (
            <>
              <p className="text-sm text-muted-foreground">
                El dashboard no ha podido hablar con la API en{" "}
                <code className="mono text-xs">{BASE_URL}</code>. No se muestra
                nada porque los datos serían inventados.
              </p>
              <div className="rounded-lg border border-[hsl(var(--border-strong))] bg-black/20 p-3">
                <div className="mb-1 inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                  <Terminal className="h-3 w-3" /> Arranca el backend
                </div>
                <code className="mono block text-xs text-foreground">
                  cd backend &amp;&amp; uvicorn app.main:app --reload
                </code>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">{error.message}</p>
          )}

          <Button onClick={reset} className="w-full">
            <RefreshCcw className="mr-2 h-3.5 w-3.5" />
            Reintentar
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
