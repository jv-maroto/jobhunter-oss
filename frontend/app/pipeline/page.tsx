"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Workflow, X } from "lucide-react";
import { KanbanBoard } from "@/components/kanban/KanbanBoard";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePipeline } from "@/hooks/useMetrics";
import { JOB_STATUSES, type Job, type JobStatus } from "@/lib/types";

function filterByCompany(
  data: Record<JobStatus, Job[]>,
  company: string,
): Record<JobStatus, Job[]> {
  const needle = company.trim().toLowerCase();
  const out = {} as Record<JobStatus, Job[]>;
  for (const s of JOB_STATUSES) {
    out[s] = (data[s] ?? []).filter(
      (j) => (j.company ?? "").toLowerCase() === needle,
    );
  }
  return out;
}

function PipelineContent() {
  const { data, isLoading } = usePipeline();
  const searchParams = useSearchParams();
  const company = searchParams.get("company")?.trim() || "";

  const shown = React.useMemo(
    () => (data && company ? filterByCompany(data, company) : data),
    [data, company],
  );

  return (
    <div className="space-y-5">
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="inline-flex items-center gap-2">
            <Workflow className="h-4 w-4 text-[hsl(var(--accent-1))]" />
            Pipeline
          </CardTitle>
          <p className="text-[11px] text-muted-foreground">
            Drag jobs between columns to transition their status.
          </p>
          {company ? (
            <div className="mt-2 inline-flex items-center gap-2">
              <Badge variant="mono" size="sm">
                Filtered · {company}
              </Badge>
              <Link
                href="/pipeline"
                className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" /> clear
              </Link>
            </div>
          ) : null}
        </CardHeader>
        <CardContent>
          {isLoading || !shown ? (
            <div className="flex gap-3">
              {Array.from({ length: 7 }).map((_, i) => (
                <Skeleton key={i} className="h-96 w-[280px] shrink-0" />
              ))}
            </div>
          ) : (
            <KanbanBoard initial={shown} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function PipelinePage() {
  return (
    <React.Suspense
      fallback={
        <div className="flex gap-3">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-96 w-[280px] shrink-0" />
          ))}
        </div>
      }
    >
      <PipelineContent />
    </React.Suspense>
  );
}
