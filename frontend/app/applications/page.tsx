"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Building2, FileText, MapPin } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useApplications } from "@/hooks/useApplications";
import { apiDate } from "@/lib/utils";

const PAGE_SIZE = 50;

export default function ApplicationsPage() {
  const [offset, setOffset] = React.useState(0);
  const [dueDate, setDueDate] = React.useState("");
  const due = dueDate ? new Date(`${dueDate}T23:59:59.999`) : null;
  const applications = useApplications({
    limit: PAGE_SIZE,
    offset,
    due_before: due && Number.isFinite(due.getTime()) ? due.toISOString() : undefined,
  });
  const items = applications.data?.items ?? [];
  const total = applications.data?.total ?? 0;

  return (
    <div className="space-y-5">
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><FileText className="h-4 w-4" />Applications</CardTitle>
          <p className="text-sm text-muted-foreground">Saved jobs, prepared documents and submitted applications. One latest record per job.</p>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <label htmlFor="applications-due" className="text-xs font-medium">Follow-ups due by</label>
            <Input id="applications-due" type="date" value={dueDate} onChange={(event) => {
              setDueDate(event.target.value);
              setOffset(0);
            }} />
          </div>
          {dueDate && <Button variant="ghost" onClick={() => { setDueDate(""); setOffset(0); }}>Clear filter</Button>}
          <Button asChild variant="outline" className="sm:ml-auto"><Link href="/jobs">Find jobs</Link></Button>
        </CardContent>
      </Card>

      {applications.isError && (
        <Card variant="outline"><CardContent className="space-y-3 pt-5">
          <p role="alert" className="text-sm text-rose-400">{applications.error instanceof Error ? applications.error.message : "Applications could not be loaded."}</p>
          <Button variant="outline" onClick={() => applications.refetch()} disabled={applications.isFetching}>Retry</Button>
        </CardContent></Card>
      )}

      {applications.isPending ? <Skeleton aria-label="Loading applications" className="h-72 w-full" /> : !applications.isError && items.length === 0 ? (
        <Card variant="glass"><CardContent className="space-y-2 py-12 text-center">
          <h2 className="font-semibold">{dueDate ? "No follow-ups due in this range" : "No applications on this page"}</h2>
          <p className="text-sm text-muted-foreground">{dueDate ? "Try a later date or clear the filter." : "Save a job or prepare an application to start your register."}</p>
        </CardContent></Card>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {items.map((application) => {
            const { job } = application;
            const submitted = apiDate(application.submitted_at ?? job.applied_at);
            const prepared = apiDate(application.prepared_at);
            const nextAction = apiDate(job.next_action_at);
            const href = application.application_id ? `/applications/${application.application_id}` : `/jobs/${job.id}`;
            return (
              <Card key={job.id} variant="glass">
                <CardHeader className="space-y-2">
                  <div className="flex items-start justify-between gap-3">
                    <Link href={href} className="min-w-0 break-words font-semibold hover:underline">{job.title || "Untitled job"}</Link>
                    <Badge variant="outline" className="shrink-0 capitalize">{job.status.replaceAll("_", " ")}</Badge>
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1"><Building2 className="h-3 w-3" />{job.company || "Company not provided"}</span>
                    <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3" />{job.location || (job.remote ? "Remote" : "Location not provided")}</span>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <dl className="grid gap-2 text-xs sm:grid-cols-2">
                    <div><dt className="text-muted-foreground">Prepared</dt><dd>{prepared?.toLocaleString() ?? "Not recorded"}</dd></div>
                    <div><dt className="text-muted-foreground">Submitted</dt><dd>{submitted?.toLocaleString() ?? "Not recorded"}</dd></div>
                  </dl>
                  {(job.next_action || nextAction) && <div className="rounded-md border border-[hsl(var(--border))] p-3 text-sm">
                    <p className="font-medium">Next action</p>
                    <p className="break-words">{job.next_action || "Follow up"}</p>
                    {nextAction && <p className="mt-1 text-xs text-muted-foreground">Due {nextAction.toLocaleString()}</p>}
                  </div>}
                  {job.notes && <p className="line-clamp-3 whitespace-pre-wrap break-words text-sm text-muted-foreground">{job.notes}</p>}
                  <Button asChild variant="outline" className="w-full"><Link href={href}>{application.application_id ? "Review application & documents" : "View job & application history"}<ArrowRight /></Link></Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <nav aria-label="Application pages" className="flex flex-wrap items-center justify-between gap-3">
        <Button variant="outline" disabled={offset === 0 || applications.isFetching} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}><ArrowLeft />Previous</Button>
        <p aria-live="polite" className="text-sm text-muted-foreground">{applications.data ? `${items.length ? offset + 1 : 0}–${items.length ? offset + items.length : 0} of ${total}` : applications.isError ? "Records unavailable" : "Loading records…"}</p>
        <Button variant="outline" disabled={!applications.data || offset + items.length >= total || applications.isFetching || applications.isError} onClick={() => setOffset(offset + PAGE_SIZE)}>Next<ArrowRight /></Button>
      </nav>
    </div>
  );
}
