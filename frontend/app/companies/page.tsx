"use client";

import Link from "next/link";
import { Building2, ArrowRight } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreBadge } from "@/components/jobs/ScoreBadge";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { useCompanies } from "@/hooks/useMetrics";
import { formatRelative } from "@/lib/utils";

export default function CompaniesPage() {
  const { data, isLoading } = useCompanies();

  if (isLoading || !data) {
    return <Skeleton className="h-96 w-full" />;
  }

  const list = Array.isArray(data) ? data : [];
  const sorted = list
    .slice()
    .sort((a, b) => (b.avg_score ?? 0) - (a.avg_score ?? 0));

  return (
    <Card variant="glass">
      <CardHeader>
        <CardTitle className="inline-flex items-center gap-2">
          <Building2 className="h-4 w-4 text-[hsl(var(--accent-1))]" />
          Companies
        </CardTitle>
        <p className="text-[11px] text-muted-foreground">
          Aggregated view by employer — sorted by average match score.
        </p>
      </CardHeader>
      <CardContent>
        <div className="overflow-hidden rounded-xl border border-[hsl(var(--border))]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Company</TableHead>
                <TableHead>Avg score</TableHead>
                <TableHead>Jobs</TableHead>
                <TableHead>Connections</TableHead>
                <TableHead>Last activity</TableHead>
                <TableHead className="text-right">Jump</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map((c, idx) => {
                const name = c.name ?? c.company ?? "—";
                const jobsCount = c.jobs_count ?? c.jobs_detected ?? 0;
                const conn = c.internal_connections ?? 0;
                return (
                  <TableRow key={`${name}-${idx}`}>
                    <TableCell className="font-medium">{name}</TableCell>
                    <TableCell>
                      <ScoreBadge score={c.avg_score} />
                    </TableCell>
                    <TableCell className="mono text-xs">{jobsCount}</TableCell>
                    <TableCell>
                      {conn > 0 ? (
                        <Badge variant="default" size="sm">
                          {conn}
                        </Badge>
                      ) : (
                        <Badge variant="outline" size="sm">
                          0
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                      {formatRelative(c.last_activity)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link
                        href={`/pipeline?company=${encodeURIComponent(name)}`}
                        className="inline-flex items-center gap-1 text-xs text-[hsl(var(--accent-1))] hover:underline"
                      >
                        View
                        <ArrowRight className="h-3 w-3" />
                      </Link>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
