"use client";

import * as React from "react";
import { toast } from "sonner";
import { X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { useUpdateJobStatus } from "@/hooks/useJobs";
import { cn } from "@/lib/utils";
import type { Job } from "@/lib/types";

const REASONS: Array<{
  id: string;
  label: string;
  destination: "rejected" | "ghosted";
}> = [
  {
    id: "link_broken",
    label: "Link broken or returns 404",
    destination: "rejected",
  },
  {
    id: "expired",
    label: "Job posting expired / closed",
    destination: "rejected",
  },
  {
    id: "already_applied",
    label: "Already applied elsewhere",
    destination: "rejected",
  },
  {
    id: "salary_too_low",
    label: "Salary too low (under 28k€)",
    destination: "rejected",
  },
  {
    id: "wrong_location",
    label: "Wrong location (no remote, not EU)",
    destination: "rejected",
  },
  {
    id: "stack_mismatch",
    label: "Stack doesn't fit my profile",
    destination: "rejected",
  },
  {
    id: "seniority_too_high",
    label: "Requires 5+ years (overqualified search)",
    destination: "rejected",
  },
  {
    id: "company_red_flag",
    label: "Company red flag / bad reviews",
    destination: "rejected",
  },
  {
    id: "no_interest",
    label: "Just not interested",
    destination: "rejected",
  },
  {
    id: "other",
    label: "Other (specify below)",
    destination: "rejected",
  },
];

export function SkipReasonDialog({
  job,
  open,
  onOpenChange,
}: {
  job: Job | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [selected, setSelected] = React.useState<string>("link_broken");
  const [extra, setExtra] = React.useState("");
  const update = useUpdateJobStatus();

  React.useEffect(() => {
    if (open) {
      setSelected("link_broken");
      setExtra("");
    }
  }, [open]);

  if (!job) return null;

  const reason = REASONS.find((r) => r.id === selected) ?? REASONS[0];

  const submit = async () => {
    const reasonLabel = reason.label;
    const note =
      extra.trim().length > 0 ? `${reasonLabel} — ${extra.trim()}` : reasonLabel;
    try {
      await update.mutateAsync({
        id: job.id,
        status: reason.destination,
        notes: note,
      });
      toast.success("Job skipped", { description: reasonLabel, duration: 4000 });
      onOpenChange(false);
    } catch {
      toast.error("Failed to skip job");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="inline-flex items-center gap-2">
            <X className="h-4 w-4 text-[hsl(var(--accent-warn))]" />
            Skip job — pick a reason
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--surface))]/40 px-3 py-2">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Job
            </div>
            <div className="text-sm font-medium truncate" title={job.title}>
              {job.title}
            </div>
            <div className="text-xs text-muted-foreground truncate">
              {job.company}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-1.5">
            {REASONS.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => setSelected(r.id)}
                className={cn(
                  "flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-xs transition-colors",
                  selected === r.id
                    ? "border-[hsl(var(--accent-1))]/60 bg-[hsl(var(--accent-1))]/10 text-foreground"
                    : "border-[hsl(var(--border))] hover:bg-white/[0.03] text-muted-foreground",
                )}
              >
                <span
                  className={cn(
                    "grid h-3.5 w-3.5 place-items-center rounded-full border shrink-0",
                    selected === r.id
                      ? "border-[hsl(var(--accent-1))]"
                      : "border-[hsl(var(--border))]",
                  )}
                >
                  {selected === r.id && (
                    <span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--accent-1))]" />
                  )}
                </span>
                {r.label}
              </button>
            ))}
          </div>

          <div>
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Notes (optional)
            </label>
            <Textarea
              value={extra}
              onChange={(e) => setExtra(e.target.value)}
              rows={2}
              placeholder="Anything useful for future filtering…"
              className="text-xs"
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={submit}
            disabled={update.isPending}
          >
            <X className="h-3.5 w-3.5" />
            Skip with this reason
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
