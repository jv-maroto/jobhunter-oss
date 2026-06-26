"use client";

import { Loader2, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { usePrepareApplication, useUpdateJobStatus } from "@/hooks/useJobs";
import { sourceFriction } from "@/lib/utils";
import type { Job } from "@/lib/types";

export function PrepareApplicationButton({
  job,
  variant = "default",
  size = "sm",
}: {
  job: Job;
  variant?: "default" | "solid" | "outline" | "glass";
  size?: "sm" | "default";
}) {
  const mutation = usePrepareApplication();
  const advance = useUpdateJobStatus();

  const markApplied = async () => {
    try {
      await advance.mutateAsync({ id: job.id, status: "applied" });
      toast.success("Marked as applied", { duration: 3000 });
    } catch {
      toast.error("Failed to update status");
    }
  };

  const friction = sourceFriction(job.source);

  const generateAndOpen = async () => {
    try {
      await mutation.mutateAsync(job.id);
      window.open(job.source_url, "_blank", "noopener,noreferrer");
      toast.success("CV + cover letter ready", {
        description:
          "Job opened in new tab. After you submit, mark it as applied to advance the pipeline.",
        action: {
          label: "I applied",
          onClick: markApplied,
        },
        duration: 15000,
      });
    } catch (e) {
      toast.error("Failed to prepare", { description: String(e) });
    }
  };

  const handle = async () => {
    if (friction.level === "hard") {
      toast.warning(`${job.source}: account setup first time`, {
        description: friction.hint,
        action: {
          label: "Continue anyway",
          onClick: generateAndOpen,
        },
        duration: 10000,
      });
      return;
    }
    await generateAndOpen();
  };

  return (
    <Button
      size={size}
      variant={variant}
      onClick={handle}
      disabled={mutation.isPending}
      shimmer={variant === "default" || variant === "solid"}
      className="group"
    >
      {mutation.isPending ? (
        <Loader2 className="animate-spin" />
      ) : (
        <Wand2 />
      )}
      Prepare
    </Button>
  );
}
