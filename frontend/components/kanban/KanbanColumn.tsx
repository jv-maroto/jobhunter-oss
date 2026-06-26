"use client";

import { useDroppable } from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { JobCard } from "@/components/jobs/JobCard";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Job, JobStatus } from "@/lib/types";

const COLUMN_LABEL: Record<JobStatus, string> = {
  detected: "Detected",
  prepared: "Prepared",
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  rejected: "Rejected",
  ghosted: "Ghosted",
};

const NEXT_STATUS: Record<JobStatus, JobStatus | null> = {
  detected: "prepared",
  prepared: "applied",
  applied: "interviewing",
  interviewing: "offer",
  offer: null,
  rejected: null,
  ghosted: null,
};

const NEXT_LABEL: Record<JobStatus, string> = {
  detected: "Move to Prepared",
  prepared: "Move to Applied",
  applied: "Move to Interviewing",
  interviewing: "Move to Offer",
  offer: "",
  rejected: "",
  ghosted: "",
};

const COLUMN_TONE: Record<JobStatus, string> = {
  detected: "from-[hsl(var(--accent-1))]/40",
  prepared: "from-[hsl(var(--accent-2))]/40",
  applied: "from-[hsl(var(--accent-1))]/40",
  interviewing: "from-[hsl(var(--score-good))]/40",
  offer: "from-[hsl(var(--score-good))]/55",
  rejected: "from-[hsl(var(--score-bad))]/40",
  ghosted: "from-muted-foreground/40",
};

function SortableJobCard({
  job,
  onAdvance,
  advanceLabel,
}: {
  job: Job;
  onAdvance?: () => void;
  advanceLabel?: string;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: job.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };
  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <JobCard
        job={job}
        compact
        onAdvance={onAdvance}
        advanceLabel={advanceLabel}
      />
    </div>
  );
}

export function KanbanColumn({
  status,
  jobs,
  onAdvance,
}: {
  status: JobStatus;
  jobs: Job[];
  onAdvance?: (job: Job, target: JobStatus) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  const nextStatus = NEXT_STATUS[status];
  const advanceLabel = NEXT_LABEL[status];

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex w-[280px] shrink-0 flex-col rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--surface))]/40 transition-colors overflow-hidden",
        isOver && "drop-active",
      )}
    >
      {/* Sticky glass header */}
      <div className="sticky top-0 z-10 flex items-center justify-between gap-2 border-b border-[hsl(var(--border))] bg-[hsl(var(--surface))]/85 backdrop-blur-md px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "h-2 w-2 rounded-full bg-gradient-to-br to-transparent",
              COLUMN_TONE[status],
            )}
            style={{
              backgroundImage:
                status === "offer"
                  ? "linear-gradient(120deg, hsl(var(--score-good)), hsl(var(--score-good)))"
                  : undefined,
            }}
          />
          <div className="text-[10px] font-semibold uppercase tracking-wider text-foreground">
            {COLUMN_LABEL[status]}
          </div>
        </div>
        <Badge variant="mono" size="sm">
          {jobs.length}
        </Badge>
      </div>
      <SortableContext
        items={jobs.map((j) => j.id)}
        strategy={verticalListSortingStrategy}
      >
        <div className="flex-1 space-y-2 p-2 min-h-[260px]">
          {jobs.length === 0 ? (
            <div className="grid place-items-center py-12 text-[11px] text-muted-foreground/50 italic">
              empty
            </div>
          ) : (
            jobs.map((job) => (
              <SortableJobCard
                key={job.id}
                job={job}
                advanceLabel={advanceLabel}
                onAdvance={
                  nextStatus && onAdvance
                    ? () => onAdvance(job, nextStatus)
                    : undefined
                }
              />
            ))
          )}
        </div>
      </SortableContext>
    </div>
  );
}
