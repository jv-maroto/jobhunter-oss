"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, ExternalLink, Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import { useJob, useUpdateJobStatus } from "@/hooks/useJobs";
import { JOB_STATUSES, JOB_TRACK_LABELS, EMPLOYMENT_LABELS, type Job, type JobStatus } from "@/lib/types";
import { formatSalary, localDateTimeInput, publicJobUrl } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ScoreBadge } from "@/components/jobs/ScoreBadge";
import { PrepareApplicationButton } from "@/components/jobs/PrepareApplicationButton";
import { QualificationChecks } from "@/components/jobs/QualificationChecks";

function Tracker({ job }: { job: Job }) {
  const [notes, setNotes] = React.useState(job.notes ?? "");
  const [action, setAction] = React.useState(job.next_action ?? "");
  const [due, setDue] = React.useState(localDateTimeInput(job.next_action_at));
  const [status, setStatus] = React.useState(job.status);
  const [error, setError] = React.useState("");
  const update = useUpdateJobStatus();
  const terminal = ["offer", "rejected", "ghosted"].includes(status);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    if (due && !action.trim() && !terminal) {
      setError("Describe the next action before setting a reminder.");
      return;
    }
    try {
      await update.mutateAsync({ id: job.id, notes: notes.trim() || null, next_action: terminal ? null : action.trim() || null, next_action_at: terminal || !due || !action.trim() ? null : new Date(due).toISOString(), ...(status !== job.status ? { status } : {}) });
      if (terminal) { setAction(""); setDue(""); }
      toast.success("Tracking details saved");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save. Your changes are still here.");
    }
  }

  return <Card variant="glass">
    <CardHeader><CardTitle>Your next action</CardTitle><p className="text-xs text-muted-foreground">Notes and reminders are stored privately in your database. They never send a message.</p></CardHeader>
    <CardContent>
      <form onSubmit={save} className="space-y-4">
        <label className="block text-sm space-y-1.5">Stage<select value={status} onChange={(event) => setStatus(event.target.value as JobStatus)} className="w-full rounded-lg border border-input bg-background px-3 py-2" disabled={update.isPending}>{JOB_STATUSES.map((stage) => <option value={stage} key={stage}>{stage.charAt(0).toUpperCase() + stage.slice(1)}</option>)}</select></label>
        {status === "applied" && job.status !== "applied" && <p className="text-xs text-muted-foreground">Choose Applied only after you have submitted the application. You can record the exact document version from its review page.</p>}
        {!terminal && <>
          <label className="block text-sm space-y-1.5">Next action<Input value={action} onChange={(event) => setAction(event.target.value)} maxLength={2000} placeholder="For example: follow up with the recruiter" disabled={update.isPending} /></label>
          <label className="block text-sm space-y-1.5">Remind me at (your local time)<Input type="datetime-local" value={due} onChange={(event) => setDue(event.target.value)} disabled={update.isPending} /></label>
        </>}
        <label className="block text-sm space-y-1.5">Private notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={20000} rows={6} disabled={update.isPending} className="w-full rounded-lg border border-input bg-background px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></label>
        {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
        <Button type="submit" disabled={update.isPending} className="w-full">{update.isPending ? <Loader2 className="animate-spin" /> : <Save />}Save tracking details</Button>
      </form>
    </CardContent>
  </Card>;
}

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const query = useJob(id);
  const job = query.data;
  if (!Number.isSafeInteger(id) || id < 1) return <p role="alert">Invalid job identifier.</p>;
  if (query.isLoading) return <Skeleton className="h-96 w-full" />;
  if (query.error || !job) return <div role="alert" className="space-y-3"><p>{query.error instanceof Error ? query.error.message : "Job not found."}</p><Button variant="outline" onClick={() => query.refetch()}>Try again</Button><Link href="/jobs" className="ml-3 underline">Back to jobs</Link></div>;
  const sourceUrl = publicJobUrl(job.source_url);
  return <div className="space-y-5">
    <Link href="/jobs" className="inline-flex gap-2 items-center text-sm text-muted-foreground hover:text-foreground"><ArrowLeft size={16} />All jobs</Link>
    <Card variant="glass"><CardHeader>
      <div className="flex flex-wrap justify-between gap-4">
        <div className="min-w-0 space-y-2"><h1 className="text-xl font-semibold break-words">{job.title}</h1><p className="text-sm text-muted-foreground">{job.company} · {job.location || "Location not stated"}</p><p className="text-xs text-muted-foreground">{JOB_TRACK_LABELS[job.track] || job.track} · {job.employment_type ? EMPLOYMENT_LABELS[job.employment_type] : "Contract not stated"} · {formatSalary(job.salary_min, job.salary_max, job.currency, job.salary_period)}</p></div>
        <ScoreBadge score={job.match_score} reason={job.rejection_reason} size="md" />
      </div>
      <div className="flex flex-wrap items-center gap-3 pt-3"><PrepareApplicationButton job={job} />{sourceUrl && <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="inline-flex gap-1.5 items-center text-sm underline underline-offset-4">Original posting<ExternalLink size={14} /></a>}<Link href="/applications" className="text-sm underline underline-offset-4">Application history</Link></div>
    </CardHeader></Card>
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="space-y-5 min-w-0">
        <QualificationChecks assessment={job.qualification_assessment} />
        {(job.key_matches.length > 0 || job.missing_skills.length > 0) && <Card variant="glass"><CardContent className="pt-5 grid gap-4 sm:grid-cols-2"><div><h2 className="font-medium text-sm mb-2">Evidence to highlight</h2><ul className="list-disc pl-5 text-sm text-muted-foreground space-y-1">{job.key_matches.map((value, index) => <li key={index}>{value}</li>)}</ul></div><div><h2 className="font-medium text-sm mb-2">Skills to verify</h2><ul className="list-disc pl-5 text-sm text-muted-foreground space-y-1">{job.missing_skills.map((value, index) => <li key={index}>{value}</li>)}</ul></div></CardContent></Card>}
        <Card variant="glass"><CardHeader><CardTitle>Job description</CardTitle></CardHeader><CardContent><div className="whitespace-pre-wrap break-words text-sm leading-relaxed text-muted-foreground">{job.description || "No description was provided. Check the original posting before preparing an application."}</div></CardContent></Card>
      </div>
      <aside><Tracker key={job.id} job={job} /></aside>
    </div>
  </div>;
}
