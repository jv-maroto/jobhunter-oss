import { ChevronRight, ExternalLink, MapPin } from "lucide-react";
import type { Job } from "@/lib/types";
import { ScoreBadge } from "@/components/jobs/ScoreBadge";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { formatSalary } from "@/lib/utils";
import { JobActionsMenu } from "@/components/jobs/JobActionsMenu";

export function JobCard({
  job,
  compact = false,
  onAdvance,
  advanceLabel,
  showActions = true,
}: {
  job: Job;
  compact?: boolean;
  /** If present, renders a "next stage" button. */
  onAdvance?: () => void;
  /** Tooltip on the advance button (e.g. "Move to Applied"). */
  advanceLabel?: string;
  /** Show the "•••" menu with move-to-any-status + delete. Default: true. */
  showActions?: boolean;
}) {
  return (
    <Card
      variant="solid"
      hover="lift"
      className="cursor-grab active:cursor-grabbing p-3"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-center gap-1.5 min-w-0">
            <div
              className="text-sm font-medium truncate text-foreground min-w-0 flex-1"
              title={job.title ?? ""}
            >
              {job.title ?? "Untitled"}
            </div>
            <a
              href={job.source_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-muted-foreground hover:text-[hsl(var(--accent-1))] shrink-0"
            >
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
          <div
            className="text-xs text-muted-foreground truncate"
            title={job.company ?? ""}
          >
            {job.company ?? "—"}
          </div>
          {!compact && (
            <div className="flex items-center gap-2 text-[10px] text-muted-foreground/80">
              <span className="inline-flex items-center gap-1 truncate">
                <MapPin className="h-2.5 w-2.5 shrink-0" />
                <span className="truncate">
                  {job.remote ? "Remote" : job.location ?? "—"}
                </span>
              </span>
              <span className="mono whitespace-nowrap">
                {formatSalary(job.salary_min, job.salary_max, job.currency)}
              </span>
            </div>
          )}
          {!compact &&
            Array.isArray(job.key_matches) &&
            job.key_matches.length > 0 && (
              <div className="flex flex-wrap gap-1 pt-1">
                {job.key_matches.slice(0, 3).map((k) => (
                  <Badge
                    key={k}
                    variant="secondary"
                    size="sm"
                    className="max-w-[180px] truncate"
                    title={k}
                  >
                    {k}
                  </Badge>
                ))}
              </div>
            )}
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          <ScoreBadge score={job.match_score ?? 0} size="md" />
          <div className="flex items-center gap-1">
            {showActions && <JobActionsMenu job={job} />}
            {onAdvance && (
              <button
                type="button"
                onPointerDown={(e) => e.stopPropagation()}
                onClick={(e) => {
                  e.stopPropagation();
                  onAdvance();
                }}
                title={advanceLabel ?? "Next stage"}
                className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-[hsl(var(--accent-1))]/40 bg-[hsl(var(--accent-1))]/10 text-[hsl(var(--accent-1))] hover:bg-[hsl(var(--accent-1))]/20 hover:border-[hsl(var(--accent-1))]/60 transition-colors"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
