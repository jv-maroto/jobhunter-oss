"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Job } from "@/lib/types";

export function EvaluateJobButton({ job }: { job: Job }) {
  const cache = useQueryClient();
  const evaluation = useMutation({
    mutationFn: () => api<Job>(`/jobs/${job.id}/evaluate`, { method: "POST" }),
    onSuccess: () => {
      for (const key of ["jobs", "job", "metrics", "pipeline"]) cache.invalidateQueries({ queryKey: [key] });
      toast.success("Evaluación disponible", { description: "El encaje no representa una probabilidad de contratación." });
    },
    onError: (error) => toast.error(error.message),
  });
  return <Button variant="outline" disabled={evaluation.isPending} onClick={() => evaluation.mutate()}>
    {evaluation.isPending ? "Evaluando…" : "Evaluar encaje con IA"}
  </Button>;
}
