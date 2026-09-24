"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Job } from "@/lib/types";

export function AvailabilityCheck({ job }: { job: Job }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  async function check() {
    setPending(true); setError(null);
    try {
      await api<Job>(`/jobs/${job.id}/availability`, { method: "POST" });
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
      await queryClient.invalidateQueries({ queryKey: ["job", job.id] });
    } catch (error) { setError(error instanceof Error ? error.message : "No se pudo comprobar la oferta"); }
    finally { setPending(false); }
  }
  const state = job.availability;
  return <div className="space-y-2 rounded-lg border border-[hsl(var(--border))] p-3 text-sm">
    <p className="font-medium">{state?.status === "active" ? "Vigencia comprobada" : state?.status === "expired" ? "Oferta cerrada o caducada" : "Vigencia sin confirmar"}</p>
    <p className="text-xs text-muted-foreground">{state?.reason || "Todavía no se ha comprobado si acepta candidaturas."}{state?.checked_at ? ` · Comprobación: ${new Date(state.checked_at).toLocaleString("es-ES")}` : ""}</p>
    <Button variant="outline" size="sm" disabled={pending} onClick={check}>{pending ? "Comprobando…" : "Comprobar vigencia"}</Button>
    {error && <p role="alert" className="text-xs text-red-400">{error}</p>}
  </div>;
}
