"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, ExternalLink, Zap, FileText, ShieldAlert, X } from "lucide-react";
import { ScoreBadge } from "@/components/jobs/ScoreBadge";
import { PrepareApplicationButton } from "@/components/jobs/PrepareApplicationButton";
import { SkipReasonDialog } from "@/components/jobs/SkipReasonDialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { sourceFriction } from "@/lib/utils";
import type { Job } from "@/lib/types";

/**
 * Compact list used on /today: shows only title, company, score and quick
 * actions. The full table lives in /jobs.
 */
export function JobsCompactList({
  jobs,
  limit = 12,
}: {
  jobs: Job[];
  limit?: number;
}) {
  const [skipping, setSkipping] = React.useState<Job | null>(null);

  if (jobs.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-[hsl(var(--border))] p-10 text-center text-sm text-muted-foreground">
        No jobs match these filters.
      </div>
    );
  }

  const shown = jobs.slice(0, limit);
  const hidden = jobs.length - shown.length;

  return (
    <>
      <ul className="divide-y divide-[hsl(var(--border))] rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--surface))]/40 overflow-hidden">
        {shown.map((job) => {
          const friction = sourceFriction(job.source);
          const FrictionIcon =
            friction.level === "easy"
              ? Zap
              : friction.level === "medium"
                ? FileText
                : ShieldAlert;
          return (
            <li
              key={job.id}
              className="row-hover flex items-center gap-3 px-3.5 py-2.5"
            >
              <ScoreBadge score={job.match_score ?? 0} />
              <div className="min-w-0 flex-1">
                <a
                  href={job.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group/link flex items-center gap-1 min-w-0"
                  title={job.title ?? ""}
                >
                  <span className="truncate text-sm font-medium group-hover/link:text-[hsl(var(--accent-1))] transition-colors">
                    {job.title ?? "Untitled"}
                  </span>
                  <ExternalLink className="h-3 w-3 shrink-0 text-muted-foreground group-hover/link:text-[hsl(var(--accent-1))] transition-colors" />
                </a>
                <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                  <span className="truncate" title={job.company ?? ""}>
                    {job.company ?? "—"}
                  </span>
                  <span className="text-muted-foreground/50">·</span>
                  <Badge
                    variant={
                      friction.level === "easy"
                        ? "default"
                        : friction.level === "medium"
                          ? "secondary"
                          : "destructive"
                    }
                    size="sm"
                    className="gap-1 shrink-0"
                    title={friction.hint}
                  >
                    <FrictionIcon className="h-2.5 w-2.5" />
                    {friction.label}
                  </Badge>
                </div>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <PrepareApplicationButton job={job} />
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setSkipping(job)}
                  title="Skip with reason"
                  className="text-muted-foreground hover:text-[hsl(var(--accent-warn))]"
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
      {hidden > 0 && (
        <div className="flex items-center justify-end pt-2">
          <Link
            href="/jobs"
            className="inline-flex items-center gap-1 text-xs text-[hsl(var(--accent-1))] hover:underline"
          >
            View all {jobs.length} jobs in full table
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}
      <SkipReasonDialog
        job={skipping}
        open={skipping !== null}
        onOpenChange={(open) => !open && setSkipping(null)}
      />
    </>
  );
}
