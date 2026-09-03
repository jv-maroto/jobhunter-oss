"use client";

/**
 * JobActionsMenu — botón "•••" en cada tarjeta del pipeline que abre un
 * Dialog con opciones de:
 *   - Move to: cualquier estado del kanban
 *   - Delete permanently (con confirm inline)
 */

import * as React from "react";
import { MoreHorizontal, Trash2, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useDeleteJob, useUpdateJobStatus } from "@/hooks/useJobs";
import { JOB_STATUSES, type Job, type JobStatus } from "@/lib/types";

const STATUS_LABEL: Record<JobStatus, string> = {
  detected: "Detected",
  prepared: "Prepared",
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  rejected: "Rejected",
  ghosted: "Ghosted",
};

export function JobActionsMenu({ job }: { job: Job }) {
  const [open, setOpen] = React.useState(false);
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const updateStatus = useUpdateJobStatus();
  const deleteJob = useDeleteJob();

  const moveTo = async (target: JobStatus) => {
    if (target === job.status) {
      setOpen(false);
      return;
    }
    try {
      await updateStatus.mutateAsync({ id: job.id, status: target });
      toast.success(`Moved to ${STATUS_LABEL[target]}`);
      setOpen(false);
    } catch {
      toast.error("Failed to update status");
    }
  };

  const doDelete = async () => {
    try {
      const res = await deleteJob.mutateAsync(job.id);
      toast.success("Job deleted", {
        description: `${res.applications} application(s) + files removed.`,
        icon: <Trash2 className="h-4 w-4" />,
      });
      setOpen(false);
      setConfirmDelete(false);
    } catch (e) {
      toast.error("Failed to delete", {
        description: String(e).slice(0, 140),
      });
    }
  };

  return (
    <>
      {/* Trigger — kebab button. stopPropagation so it doesn't grab drag */}
      <button
        type="button"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
        title="Actions"
        className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-[hsl(var(--border))] bg-transparent text-muted-foreground hover:bg-white/5 hover:text-foreground transition-colors"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      <Dialog
        open={open}
        onOpenChange={(v) => {
          setOpen(v);
          if (!v) setConfirmDelete(false);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="inline-flex items-center gap-2">
              <ArrowRight className="h-4 w-4 text-[hsl(var(--accent-1))]" />
              <span className="truncate">{job.title ?? `Job #${job.id}`}</span>
            </DialogTitle>
            <p className="text-[11px] text-muted-foreground truncate">
              {job.company ?? "—"} · currently{" "}
              <span className="mono">{STATUS_LABEL[job.status as JobStatus] ?? job.status}</span>
            </p>
          </DialogHeader>

          {!confirmDelete ? (
            <div className="space-y-3">
              <div>
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Move to
                </label>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  {JOB_STATUSES.map((s) => {
                    const current = s === job.status;
                    return (
                      <button
                        key={s}
                        type="button"
                        disabled={current || updateStatus.isPending}
                        onClick={() => moveTo(s)}
                        className={
                          "rounded-md border px-3 py-2 text-xs text-left transition-colors " +
                          (current
                            ? "border-[hsl(var(--border))] bg-white/5 text-muted-foreground cursor-not-allowed"
                            : "border-[hsl(var(--border))] hover:bg-white/5 hover:border-[hsl(var(--accent-1))]/60 text-foreground")
                        }
                      >
                        {STATUS_LABEL[s]}
                        {current && (
                          <span className="text-[9px] ml-1 mono">(current)</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              <DialogFooter className="flex-wrap gap-2 pt-2">
                <Button variant="outline" onClick={() => setOpen(false)}>
                  Close
                </Button>
                <Button
                  variant="outline"
                  className="border-red-500/40 text-red-300 hover:bg-red-500/10 hover:border-red-500/60"
                  onClick={() => setConfirmDelete(true)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete permanently
                </Button>
              </DialogFooter>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-xs">
                <div className="font-semibold text-red-200 mb-1">
                  Delete this job permanently?
                </div>
                <div className="text-red-100/80">
                  This removes the job row, all applications for it, the
                  application folder in <span className="mono">data/applications/</span>,
                  and the <span className="mono">cvs-out/</span> subfolder(s) associated.
                  There is no undo.
                </div>
              </div>
              <DialogFooter className="gap-2">
                <Button
                  variant="outline"
                  onClick={() => setConfirmDelete(false)}
                >
                  Cancel
                </Button>
                <Button
                  className="bg-red-600 text-white hover:bg-red-700"
                  disabled={deleteJob.isPending}
                  onClick={doDelete}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Yes, delete
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
