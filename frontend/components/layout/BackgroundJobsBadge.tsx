"use client";

/**
 * BackgroundJobsBadge — pill visible in TopBar when the backend is
 * running any long-running task (scrape, trending posts, weekly devlog).
 *
 * - Zero jobs running → renders nothing.
 * - One job running → single pill with spinner + label + progress.
 * - Multiple → count badge + tooltip listing each job.
 *
 * Clicking a pill jumps to the page related to that job so the user can
 * see the detail (jobs table, linkedin drafts, etc.).
 */

import Link from "next/link";
import { Loader2 } from "lucide-react";
import { useBackgroundJobs } from "@/hooks/useBackgroundJobs";
import { cn } from "@/lib/utils";

export function BackgroundJobsBadge() {
  const jobs = useBackgroundJobs();
  if (jobs.length === 0) return null;

  if (jobs.length === 1) {
    const job = jobs[0];
    const content = (
      <span className="inline-flex items-center gap-1.5">
        <Loader2 className="h-3 w-3 animate-spin" />
        <span className="font-medium">{job.label}</span>
        {job.progress && (
          <span className="hidden sm:inline text-muted-foreground">
            · {job.progress}
          </span>
        )}
      </span>
    );
    return (
      <Link
        href={job.href ?? "#"}
        title={`${job.label}${job.progress ? " — " + job.progress : ""}`}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] transition-colors",
          "border-[hsl(var(--accent-1))]/40 text-[hsl(var(--accent-1))] bg-[hsl(var(--accent-1))]/5",
          "hover:bg-[hsl(var(--accent-1))]/10",
        )}
      >
        {content}
      </Link>
    );
  }

  // Multiple jobs
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px]",
        "border-[hsl(var(--accent-1))]/40 text-[hsl(var(--accent-1))] bg-[hsl(var(--accent-1))]/5",
      )}
      title={jobs
        .map((j) => `${j.label}${j.progress ? " — " + j.progress : ""}`)
        .join("\n")}
    >
      <Loader2 className="h-3 w-3 animate-spin" />
      <span className="font-medium">
        {jobs.length} tareas en curso
      </span>
    </div>
  );
}
