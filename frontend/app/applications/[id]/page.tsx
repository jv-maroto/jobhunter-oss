"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle2, Copy, Download, ExternalLink, Save } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useApplication, useApplicationVersions, useSaveApplicationCover } from "@/hooks/useApplications";
import { usePrepareApplication, useUpdateJobStatus } from "@/hooks/useJobs";
import { BASE_URL } from "@/lib/api";
import type { ApplicationReview } from "@/lib/types";
import { apiDate, publicJobUrl } from "@/lib/utils";

export default function ApplicationPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const application = useApplication(id);
  if (!Number.isSafeInteger(id) || id <= 0) {
    return <p role="alert">Invalid application. <Link href="/applications" className="underline">Back to applications</Link></p>;
  }
  if (application.isPending) return <Skeleton aria-label="Loading application" className="h-96 w-full" />;
  if (!application.data) return (
    <Card><CardContent className="space-y-3 pt-5">
      <p role="alert">{application.error instanceof Error ? application.error.message : "Application could not be loaded."}</p>
      <Button variant="outline" onClick={() => application.refetch()}>Retry</Button>
      <Button asChild variant="ghost"><Link href="/applications">Back to applications</Link></Button>
    </CardContent></Card>
  );
  return <ApplicationEditor key={id} id={id} review={application.data} version={application.dataUpdatedAt} />;
}

function ApplicationEditor({ id, review, version }: { id: number; review: ApplicationReview; version: number }) {
  const router = useRouter();
  const save = useSaveApplicationCover(id);
  const update = useUpdateJobStatus();
  const prepare = usePrepareApplication();
  const versions = useApplicationVersions(id);
  const [draft, setDraft] = React.useState<string | null>(null);
  const [submittedDate, setSubmittedDate] = React.useState("");
  const [recorded, setRecorded] = React.useState(false);
  const [saveError, setSaveError] = React.useState("");
  const [submitError, setSubmitError] = React.useState("");
  const letter = draft ?? review.cover_letter_content ?? "";
  const dirty = draft !== null && draft !== (review.cover_letter_content ?? "");
  const editable = ["prepared", "draft"].includes(review.status) && !review.submitted_at && !recorded;
  const pending = save.isPending || update.isPending || prepare.isPending;
  const originalUrl = publicJobUrl(review.job.source_url);
  const cvUrl = review.cv_url === `/applications/${id}/cv` ? `${BASE_URL}${review.cv_url}` : null;
  const coverUrl = review.cover_url === `/applications/${id}/cover` ? `${BASE_URL}${review.cover_url}?v=${version}` : null;
  const submitted = apiDate(review.submitted_at);
  const prepared = apiDate(review.prepared_at);

  React.useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function guardNavigation(event: { preventDefault: () => void }) {
    if (dirty && !window.confirm("Leave without saving your cover-letter changes?")) event.preventDefault();
  }

  async function saveLetter() {
    if (!editable || !dirty || !letter.trim() || pending) return;
    setSaveError("");
    try {
      await save.mutateAsync(letter);
      setDraft(null);
      toast.success("Cover letter and PDF saved");
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "Could not save. Your draft is still here.");
    }
  }

  async function recordSubmission() {
    if (!editable || dirty || pending) return;
    const date = submittedDate ? new Date(submittedDate) : null;
    if (date && (!Number.isFinite(date.getTime()) || date.getTime() > Date.now())) {
      setSubmitError("Choose the actual submission time, no later than now.");
      return;
    }
    setSubmitError("");
    try {
      await update.mutateAsync({ id: review.job.id, status: "applied", application_id: id, ...(date ? { applied_at: date.toISOString() } : {}) });
      setRecorded(true);
      toast.success("Submission recorded");
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Could not record the submission. Please retry.");
    }
  }

  return (
    <div className="space-y-5">
      <Button asChild variant="ghost"><Link href="/applications" onNavigate={guardNavigation}><ArrowLeft />Applications</Link></Button>

      <Card variant="glass">
        <CardHeader className="space-y-3">
          <div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className="capitalize">{review.status.replaceAll("_", " ")}</Badge><span className="text-xs text-muted-foreground">Application #{id}</span></div>
          <h1 className="break-words text-xl font-semibold">{review.job.title || "Untitled job"}</h1>
          <p className="text-sm text-muted-foreground">{review.job.company || "Company not provided"}{review.job.location ? ` · ${review.job.location}` : ""}</p>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">Prepared {prepared?.toLocaleString() ?? "date not recorded"}{submitted ? ` · Submitted ${submitted.toLocaleString()}` : recorded ? " · Submission recorded" : " · This version has no recorded submission"}</p>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline"><Link href={`/jobs/${review.job.id}`} onNavigate={guardNavigation}>Notes & next action</Link></Button>
            {originalUrl && <Button asChild variant="outline"><a href={originalUrl} target="_blank" rel="noopener noreferrer">Original job<ExternalLink /></a></Button>}
          </div>
        </CardContent>
      </Card>

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <Card variant="glass">
          <CardHeader><CardTitle>Cover letter</CardTitle><p className="text-sm text-muted-foreground">{editable ? "Review the wording before sending. Saving updates this application's text and PDF." : "This version is read-only. Prepare a new version to change its documents."}</p></CardHeader>
          <CardContent className="space-y-3">
            <label htmlFor="cover-letter" className="text-sm font-medium">Letter text</label>
            <Textarea id="cover-letter" aria-describedby="cover-state" value={letter} onChange={(event) => { setDraft(event.target.value); setSaveError(""); }} readOnly={!editable} disabled={pending} maxLength={20000} rows={20} className="min-h-80" />
            <p id="cover-state" role="status" className={`text-xs ${dirty ? "text-amber-400" : "text-muted-foreground"}`}>{dirty ? "Unsaved changes. Save before downloading the cover PDF or recording this version as submitted." : "Showing the saved letter."}</p>
            {saveError && <p role="alert" className="text-sm text-rose-400">{saveError} Your unsaved text is preserved.</p>}
            <div className="flex flex-wrap gap-2">
              {editable && <Button onClick={saveLetter} disabled={!dirty || !letter.trim() || pending}><Save />{save.isPending ? "Saving…" : "Save letter & PDF"}</Button>}
              <Button variant="outline" disabled={!letter.trim() || pending} onClick={async () => {
                try { await navigator.clipboard.writeText(letter); toast.success(dirty ? "Draft text copied" : "Letter copied"); }
                catch { toast.error("Clipboard unavailable. Select and copy the letter text instead."); }
              }}><Copy />{dirty ? "Copy draft text" : "Copy letter text"}</Button>
              {dirty && <Button variant="ghost" disabled={pending} onClick={() => { if (window.confirm("Discard your unsaved letter changes?")) { setDraft(null); setSaveError(""); } }}>Discard edits</Button>}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card variant="glass">
            <CardHeader><CardTitle>Saved documents</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2"><h2 className="text-sm font-medium">CV</h2>
                <p className="break-words text-xs text-muted-foreground">{review.cv_source_filename ? `Source: ${review.cv_source_filename.split(/[\\/]/).pop()}` : "CV prepared for this application."}</p>
                {cvUrl ? <Button asChild variant="outline" className="w-full"><a href={cvUrl} target="_blank" rel="noopener noreferrer"><Download />Open CV PDF</a></Button> : <p className="text-sm text-muted-foreground">No CV file recorded.</p>}
              </div>
              <div className="space-y-2"><h2 className="text-sm font-medium">Cover letter</h2>
                {dirty || save.isPending ? <p className="text-xs text-amber-400">Save your changes to enable the current cover PDF.</p> : coverUrl ? <Button asChild variant="outline" className="w-full"><a href={coverUrl} target="_blank" rel="noopener noreferrer"><Download />Open saved cover PDF</a></Button> : <p className="text-sm text-muted-foreground">No cover PDF recorded.</p>}
              </div>
              <details className="border-t border-[hsl(var(--border))] pt-3">
                <summary className="cursor-pointer text-sm font-medium">Document versions{versions.data ? ` (${versions.data.length})` : ""}</summary>
                <div className="mt-3 space-y-2">
                  {versions.isPending && <p className="text-xs text-muted-foreground">Loading versions…</p>}
                  {versions.isError && <div className="space-y-2"><p role="alert" className="text-xs text-rose-400">Versions could not be loaded.</p><Button size="sm" variant="outline" disabled={versions.isFetching} onClick={() => versions.refetch()}>Retry versions</Button></div>}
                  <ul className="space-y-2">
                    {(versions.data ?? []).map((entry) => {
                      if (!entry.application_id) return null;
                      const current = entry.application_id === id;
                      const date = apiDate(entry.submitted_at ?? entry.prepared_at);
                      const label = <><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">Version #{entry.application_id}</span><span className="capitalize text-muted-foreground">{entry.status.replaceAll("_", " ")}</span></div><p className="mt-1 text-muted-foreground">{entry.submitted_at ? "Submitted" : "Prepared"} {date?.toLocaleString() ?? "date not recorded"}{current ? " · Current version" : ""}</p></>;
                      return <li key={entry.application_id}>{current ? <div aria-current="page" className="rounded-md border border-[hsl(var(--accent-1))]/40 p-3 text-xs">{label}</div> : <Link href={`/applications/${entry.application_id}`} onNavigate={guardNavigation} className="block rounded-md border border-[hsl(var(--border))] p-3 text-xs hover:border-[hsl(var(--accent-1))]/40">{label}</Link>}</li>;
                    })}
                  </ul>
                  {!versions.isPending && !versions.isError && !versions.data?.length && <p className="text-xs text-muted-foreground">No document versions recorded.</p>}
                </div>
              </details>
            </CardContent>
          </Card>

          <Card variant="glass">
            <CardHeader><CardTitle>Submission</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {submitted || recorded ? <p role="status" className="text-sm">{submitted ? `Submission recorded on ${submitted.toLocaleString()}.` : "Submission recorded."}</p> : editable ? <>
                <p className="text-sm text-muted-foreground">Submit through the employer&apos;s application process, then record it here.</p>
                <label htmlFor="submitted-at" className="block text-xs font-medium">Actual submission time (optional)</label>
                <Input id="submitted-at" type="datetime-local" value={submittedDate} onChange={(event) => { setSubmittedDate(event.target.value); setSubmitError(""); }} disabled={pending} />
                <p className="text-xs text-muted-foreground">Leave blank to record the current time.</p>
                <Button className="h-auto min-h-9 w-full whitespace-normal py-2" disabled={dirty || pending} onClick={recordSubmission}><CheckCircle2 />{update.isPending ? "Recording…" : "I submitted this application"}</Button>
              </> : <p className="text-sm text-muted-foreground">This application version is closed.</p>}
              {submitError && <p role="alert" className="text-sm text-rose-400">{submitError}</p>}
              {!editable && <Button variant="outline" className="h-auto min-h-9 w-full whitespace-normal py-2" disabled={pending || dirty} onClick={async () => {
                setSubmitError("");
                try {
                  const result = await prepare.mutateAsync(review.job.id);
                  if (!Number.isSafeInteger(result.application_id) || result.application_id <= 0) throw new Error("The new application could not be opened.");
                  router.push(`/applications/${result.application_id}`);
                } catch (error) { setSubmitError(error instanceof Error ? error.message : "Could not prepare a new version."); }
              }}>{prepare.isPending ? "Preparing…" : "Prepare a new version"}</Button>}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
