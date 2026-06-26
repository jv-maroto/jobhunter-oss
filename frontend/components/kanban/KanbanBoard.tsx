"use client";

import * as React from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/kanban/KanbanColumn";
import { JobCard } from "@/components/jobs/JobCard";
import { useUpdateJobStatus } from "@/hooks/useJobs";
import { toast } from "sonner";
import { JOB_STATUSES, type Job, type JobStatus } from "@/lib/types";

export function KanbanBoard({ initial }: { initial: Record<JobStatus, Job[]> }) {
  const [columns, setColumns] =
    React.useState<Record<JobStatus, Job[]>>(initial);
  const initialRef = React.useRef(initial);
  React.useEffect(() => {
    if (initialRef.current === initial) return;
    initialRef.current = initial;
    setColumns(initial);
  }, [initial]);

  const [activeId, setActiveId] = React.useState<number | null>(null);
  const update = useUpdateJobStatus();
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  );

  const findContainer = (id: number): JobStatus | undefined => {
    return JOB_STATUSES.find((s) => columns[s].some((j) => j.id === id));
  };

  const findJob = (id: number): Job | undefined => {
    for (const s of JOB_STATUSES) {
      const j = columns[s].find((x) => x.id === id);
      if (j) return j;
    }
    return undefined;
  };

  const handleDragStart = (e: DragStartEvent) => {
    setActiveId(Number(e.active.id));
  };

  const handleDragEnd = async (e: DragEndEvent) => {
    setActiveId(null);
    const jobId = Number(e.active.id);
    if (!e.over) return;
    const overId = e.over.id;

    const sourceStatus = findContainer(jobId);
    if (!sourceStatus) return;

    const targetStatus = (JOB_STATUSES as readonly string[]).includes(
      String(overId),
    )
      ? (String(overId) as JobStatus)
      : findContainer(Number(overId));

    if (!targetStatus || targetStatus === sourceStatus) return;

    const job = findJob(jobId);
    if (!job) return;

    setColumns((prev) => {
      const next = { ...prev };
      next[sourceStatus] = next[sourceStatus].filter((j) => j.id !== jobId);
      next[targetStatus] = [...next[targetStatus], { ...job, status: targetStatus }];
      return next;
    });

    try {
      await update.mutateAsync({ id: jobId, status: targetStatus });
      toast.success(`Moved to ${targetStatus}`);
    } catch {
      toast.error("Failed to update status");
    }
  };

  const activeJob = activeId !== null ? findJob(activeId) : null;

  const advanceJob = async (job: Job, target: JobStatus) => {
    const source = findContainer(job.id);
    if (!source || source === target) return;

    setColumns((prev) => {
      const next = { ...prev };
      next[source] = next[source].filter((j) => j.id !== job.id);
      next[target] = [...next[target], { ...job, status: target }];
      return next;
    });

    try {
      await update.mutateAsync({ id: job.id, status: target });
      toast.success(`Moved to ${target}`, {
        action: {
          label: "Undo",
          onClick: async () => {
            setColumns((prev) => {
              const next = { ...prev };
              next[target] = next[target].filter((j) => j.id !== job.id);
              next[source] = [...next[source], { ...job, status: source }];
              return next;
            });
            try {
              await update.mutateAsync({ id: job.id, status: source });
            } catch {
              /* noop */
            }
          },
        },
        duration: 5000,
      });
    } catch {
      // rollback
      setColumns((prev) => {
        const next = { ...prev };
        next[target] = next[target].filter((j) => j.id !== job.id);
        next[source] = [...next[source], { ...job, status: source }];
        return next;
      });
      toast.error("Failed to advance");
    }
  };

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-3 overflow-x-auto pb-4 -mx-1 px-1">
        {JOB_STATUSES.map((s) => (
          <KanbanColumn
            key={s}
            status={s}
            jobs={columns[s]}
            onAdvance={advanceJob}
          />
        ))}
      </div>
      <DragOverlay>
        {activeJob ? (
          <div className="drag-preview">
            <JobCard job={activeJob} compact />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
