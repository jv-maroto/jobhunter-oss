"use client";

import { JOB_TRACK_LABELS, type JobTrack } from "@/lib/types";
import { useLang } from "@/lib/i18n";

export function TrackFilter({ value, onChange }: {
  value?: JobTrack;
  onChange: (track?: JobTrack) => void;
}) {
  const { lang } = useLang();
  return (
    <label className="flex min-w-0 flex-col gap-1 text-xs text-muted-foreground">
      {lang === "es" ? "Familia profesional" : "Role family"}
      <select
        className="max-w-full rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--surface))] px-3 py-2 text-sm text-foreground"
        value={value ?? "all"}
        onChange={(event) => onChange(event.target.value === "all" ? undefined : event.target.value as JobTrack)}
      >
        <option value="all">{lang === "es" ? "Todas las familias" : "All role families"}</option>
        {Object.entries(JOB_TRACK_LABELS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
      </select>
    </label>
  );
}
