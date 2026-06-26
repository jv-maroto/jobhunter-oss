"use client";

import * as React from "react";
import { ExternalLink, MapPin, Globe, X } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ScoreBadge } from "@/components/jobs/ScoreBadge";
import { PrepareApplicationButton } from "@/components/jobs/PrepareApplicationButton";
import { SkipReasonDialog } from "@/components/jobs/SkipReasonDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  formatSalary,
  formatRelative,
  detectLanguage,
  languageLabel,
  sourceFriction,
} from "@/lib/utils";
import { Zap, FileText, ShieldAlert } from "lucide-react";
import type { Job } from "@/lib/types";

export function JobTable({ jobs }: { jobs: Job[] }) {
  const [skipping, setSkipping] = React.useState<Job | null>(null);

  if (jobs.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-[hsl(var(--border))] p-12 text-center text-sm text-muted-foreground">
        No jobs match these filters.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--surface))]/40">
      <div className="overflow-x-auto">
        <Table className="w-full" style={{ tableLayout: "fixed" }}>
          <TableHeader>
            <TableRow>
              <TableHead
                className="w-[68px]"
                title="Match score (0-100) — probability the job aligns with your CV. Computed by Claude against your skills & projects."
              >
                Match %
              </TableHead>
              <TableHead>Title</TableHead>
              <TableHead className="w-[150px]">Company</TableHead>
              <TableHead className="w-[120px] hidden md:table-cell">
                Where
              </TableHead>
              <TableHead className="w-[56px] hidden md:table-cell">Lang</TableHead>
              <TableHead className="w-[110px] hidden lg:table-cell">Apply</TableHead>
              <TableHead className="w-[78px] hidden lg:table-cell">Salary</TableHead>
              <TableHead className="w-[78px] hidden md:table-cell">Source</TableHead>
              <TableHead className="w-[86px] hidden md:table-cell">Posted</TableHead>
              <TableHead className="w-[148px] text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {jobs.map((job) => {
              const matches = Array.isArray(job.key_matches) ? job.key_matches : [];
              const title = job.title ?? "Untitled";
              const company = job.company ?? "—";
              const lang = languageLabel(
                detectLanguage(job.title, job.description, job.company),
              );
              const friction = sourceFriction(job.source);
              const FrictionIcon =
                friction.level === "easy"
                  ? Zap
                  : friction.level === "medium"
                    ? FileText
                    : ShieldAlert;
              const frictionVariant: "default" | "secondary" | "destructive" =
                friction.level === "easy"
                  ? "default"
                  : friction.level === "medium"
                    ? "secondary"
                    : "destructive";
              return (
                <TableRow key={job.id}>
                  <TableCell>
                    <ScoreBadge score={job.match_score ?? 0} />
                  </TableCell>
                  <TableCell className="font-medium min-w-0">
                    <a
                      href={job.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group/link block min-w-0"
                      title={title}
                    >
                      <span className="flex items-center gap-1 min-w-0">
                        <span className="truncate group-hover/link:text-[hsl(var(--accent-1))] transition-colors">
                          {title}
                        </span>
                        <ExternalLink className="h-3 w-3 shrink-0 text-muted-foreground group-hover/link:text-[hsl(var(--accent-1))] transition-colors" />
                      </span>
                    </a>
                    {matches.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {matches.slice(0, 2).map((k) => (
                          <Badge
                            key={k}
                            variant="secondary"
                            size="sm"
                            className="max-w-[200px] truncate"
                            title={k}
                          >
                            {k}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground min-w-0">
                    <span className="block truncate" title={company}>
                      {company}
                    </span>
                  </TableCell>
                  <TableCell className="hidden md:table-cell min-w-0">
                    {job.remote ? (
                      <Badge
                        variant="default"
                        size="sm"
                        className="gap-1 max-w-full"
                        title={job.location ?? "Remote"}
                      >
                        <Globe className="h-3 w-3 shrink-0" />
                        Remote
                      </Badge>
                    ) : (
                      <span
                        className="inline-flex items-center gap-1 text-xs text-muted-foreground max-w-full"
                        title={job.location ?? ""}
                      >
                        <MapPin className="h-3 w-3 shrink-0" />
                        <span className="truncate">{job.location ?? "—"}</span>
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <Badge
                      variant="outline"
                      size="sm"
                      className="gap-1 mono"
                      title={`Detected language: ${lang.label}`}
                    >
                      {lang.flag && (
                        <span className="leading-none">{lang.flag}</span>
                      )}
                      {lang.label}
                    </Badge>
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    <Badge
                      variant={frictionVariant}
                      size="sm"
                      className="gap-1"
                      title={friction.hint}
                    >
                      <FrictionIcon className="h-3 w-3 shrink-0" />
                      {friction.label}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground mono text-xs hidden lg:table-cell whitespace-nowrap">
                    {formatSalary(job.salary_min, job.salary_max, job.currency)}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <Badge variant="mono" className="capitalize">
                      {job.source ?? "—"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-xs hidden md:table-cell whitespace-nowrap">
                    {formatRelative(job.posted_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex items-center justify-end gap-1.5">
                      <PrepareApplicationButton job={job} />
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setSkipping(job)}
                        title="Skip this job with a reason"
                        className="text-muted-foreground hover:text-[hsl(var(--accent-warn))]"
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <SkipReasonDialog
        job={skipping}
        open={skipping !== null}
        onOpenChange={(open) => !open && setSkipping(null)}
      />
    </div>
  );
}
