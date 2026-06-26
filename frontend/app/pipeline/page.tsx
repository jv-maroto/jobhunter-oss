"use client";

import { Workflow } from "lucide-react";
import { KanbanBoard } from "@/components/kanban/KanbanBoard";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePipeline } from "@/hooks/useMetrics";

export default function PipelinePage() {
  const { data, isLoading } = usePipeline();

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
        </CardHeader>
        <CardContent>
          {isLoading || !data ? (
            <div className="flex gap-3">
              {Array.from({ length: 7 }).map((_, i) => (
                <Skeleton key={i} className="h-96 w-[280px] shrink-0" />
              ))}
            </div>
          ) : (
            <KanbanBoard initial={data} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
