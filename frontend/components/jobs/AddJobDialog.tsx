"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { publicJobUrl } from "@/lib/utils";
import type { Job } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

export function AddJobDialog() {
  const [open, setOpen] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState("");
  const router = useRouter();
  const cache = useQueryClient();

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const value = (key: string) => String(form.get(key) ?? "").trim();
    const url = value("url");
    if (url && !publicJobUrl(url)) {
      setError("Use an HTTP or HTTPS job link without embedded credentials.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await api<{ job: Job; created: boolean }>("/jobs/import", {
        method: "POST",
        body: JSON.stringify({ title: value("title"), company: value("company"), description: value("description"), url: url || null, location: value("location"), remote: form.get("remote") === "on" }),
      });
      await cache.invalidateQueries({ queryKey: ["jobs"] });
      cache.invalidateQueries({ queryKey: ["applications"] });
      toast.success(result.created ? "Job saved" : "This job is already saved");
      setOpen(false);
      router.push(`/jobs/${result.job.id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save this job. Your text is still here.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!saving) { setOpen(next); setError(""); } }}>
      <DialogTrigger asChild><Button size="sm"><Plus />Add job</Button></DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90dvh] overflow-y-auto" onInteractOutside={(event) => event.preventDefault()} onEscapeKeyDown={(event) => { if (saving) event.preventDefault(); }}>
        <DialogHeader>
          <DialogTitle>Save a job from any board</DialogTitle>
          <DialogDescription>Paste the posting and keep its source link. Saved jobs stay in your workspace even when they fall outside your search preferences.</DialogDescription>
        </DialogHeader>
        <form onSubmit={save} className="space-y-4">
          <fieldset disabled={saving} className="space-y-4 disabled:opacity-70">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1.5 text-sm block">Job title<Input name="title" required maxLength={512} autoFocus /></label>
              <label className="space-y-1.5 text-sm block">Company<Input name="company" required maxLength={256} /></label>
            </div>
            <label className="space-y-1.5 text-sm block">Posting URL (optional)<Input name="url" type="url" maxLength={1024} placeholder="https://…" /></label>
            <div className="grid gap-3 sm:grid-cols-2 sm:items-end">
              <label className="space-y-1.5 text-sm block">Location (as stated)<Input name="location" maxLength={256} /></label>
              <label className="flex items-center gap-2 text-sm py-2"><input name="remote" type="checkbox" />The posting offers remote work</label>
            </div>
            <label className="space-y-1.5 text-sm block">Full job description<textarea name="description" required maxLength={100000} rows={10} className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" placeholder="Include responsibilities, qualifications and any language or location requirements." /></label>
          </fieldset>
          {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" type="button" disabled={saving} onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={saving}>{saving ? <Loader2 className="animate-spin" /> : <Plus />}{saving ? "Saving…" : "Save and review fit"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
