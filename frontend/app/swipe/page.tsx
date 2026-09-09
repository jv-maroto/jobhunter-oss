"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import {
  Banknote,
  Building2,
  CheckCircle2,
  ExternalLink,
  FileText,
  Globe2,
  MapPin,
  Clock3,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useSwipeJobs,
  usePrepareApplication,
  useUpdateJobStatus,
} from "@/hooks/useJobs";
import { EMPLOYMENT_LABELS, JOB_TRACK_LABELS, type Job, type JobTrack, type SalaryBand } from "@/lib/types";
import { cn, formatSalary, publicJobUrl } from "@/lib/utils";
import { TrackFilter } from "@/components/jobs/TrackFilter";
import { ScoreBadge } from "@/components/jobs/ScoreBadge";
import { useLang } from "@/lib/i18n";

const BAND_LABEL: Record<SalaryBand, string> = {
  high: "🤑 alto",
  mid: "💵 medio",
  low: "🪙 bajo",
  unknown: "❓ ¿?",
};
const BAND_COLOR: Record<SalaryBand, string> = {
  high: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  mid: "bg-sky-500/15 text-sky-300 border-sky-500/40",
  low: "bg-zinc-500/15 text-zinc-300 border-zinc-500/40",
  unknown: "bg-amber-500/10 text-amber-300/70 border-amber-500/30",
};

export default function SwipePage() {
  const router = useRouter();
  const { t } = useLang();
  const [track, setTrack] = React.useState<JobTrack | undefined>(undefined);
  const [remoteOnly, setRemoteOnly] = React.useState(false);
  const [minBand, setMinBand] = React.useState<SalaryBand | undefined>(undefined);
  const [handled, setHandled] = React.useState<number[]>([]);
  const [direction, setDirection] = React.useState<-1 | 0 | 1>(0);

  const query = useSwipeJobs({
    track,
    remote_only: remoteOnly,
    min_band: minBand,
  });
  const prepare = usePrepareApplication();
  const updateStatus = useUpdateJobStatus();

  React.useEffect(() => {
    setHandled([]);
  }, [track, remoteOnly, minBand]);

  const jobs = (query.data ?? []).filter((job) => !handled.includes(job.id));
  const current = jobs[0];
  const next = jobs[1];
  const pending = prepare.isPending || updateStatus.isPending;

  const advance = (dir: -1 | 1) => {
    setDirection(dir);
    if (current) setHandled((ids) => [...ids, current.id]);
  };

  const onSkip = async () => {
    if (!current || pending) return;
    try {
      await updateStatus.mutateAsync({
        id: current.id,
        status: "rejected",
        notes: "Skipped from swipe",
      });
      advance(-1);
    } catch {
      toast.error("No se pudo descartar. Inténtalo de nuevo.");
    }
  };

  const onLater = () => {
    if (!current || pending) return;
    advance(1);
  };

  const onPrepare = async () => {
    if (!current || pending) return;
    try {
      toast.loading(t("preparing_application"), { id: `prep-${current.id}` });
      const result = await prepare.mutateAsync(current.id);
      toast.success(t("application_documents_ready"), {
        id: `prep-${current.id}`,
        icon: <FileText className="h-4 w-4" />,
      });
      router.push(`/applications/${result.application_id}`);
    } catch (e) {
      toast.error(t("prepare_application_failed"), {
        id: `prep-${current.id}`,
        description: String(e).slice(0, 120),
      });
    }
  };

  return (
    <div className="space-y-5">
      {/* Track tabs */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <TrackFilter value={track} onChange={setTrack} />

        <div className="flex items-center gap-2 flex-wrap">
          <Toggle active={remoteOnly} onClick={() => setRemoteOnly((v) => !v)}>
            <Globe2 className="h-3.5 w-3.5" /> Solo remoto
          </Toggle>
          <BandFilter value={minBand} onChange={setMinBand} />
          <span className="text-[11px] text-muted-foreground mono">
            {jobs.length > 0
              ? `${jobs.length} pendientes`
              : "—"}
          </span>
        </div>
      </div>

      {/* Card stack */}
      <div className="relative mx-auto max-w-2xl h-[520px]">
        {query.isLoading && <Skeleton className="absolute inset-0 rounded-2xl" />}

        {!query.isLoading && !query.error && jobs.length === 0 && (
          <div className="absolute inset-0 grid place-items-center text-center text-muted-foreground">
            <div>
              <p className="text-sm">No quedan ofertas pendientes en este filtro.</p>
              <p className="text-xs mt-1">
                Lanza scraping desde Jobs o cambia los filtros.
              </p>
            </div>
          </div>
        )}

        {query.error && <div role="alert" className="absolute inset-0 grid place-items-center text-sm"><div>No se pudieron cargar las ofertas. <button className="underline" onClick={() => void query.refetch()}>Reintentar</button></div></div>}

        {/* Card debajo (peek) */}
        {next && (
          <div className="absolute inset-x-4 top-3 h-[510px] rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--surface))]/30" />
        )}

        {/* Card actual */}
        <AnimatePresence mode="popLayout">
          {current && (
            <motion.div
              key={current.id}
              initial={{ scale: 0.95, opacity: 0, y: 16 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{
                x: direction === -1 ? -500 : direction === 1 ? 500 : 0,
                opacity: 0,
                rotate: direction === -1 ? -8 : 8,
                transition: { duration: 0.25 },
              }}
              transition={{ type: "spring", stiffness: 320, damping: 32 }}
              className="absolute inset-0"
            >
              <SwipeCard job={current} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Action buttons */}
      {current && (
        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-4">
          <ActionBtn
            onClick={onSkip}
            color="rose"
            label="Skip"
            disabled={pending}
            icon={<X className="h-5 w-5" />}
          />
          <ActionBtn
            onClick={onLater}
            color="amber"
            label="Más tarde"
            disabled={pending}
            icon={<Clock3 className="h-5 w-5" />}
          />
          <ActionBtn
            onClick={onPrepare}
            color="emerald"
            label={t("prepare_application")}
            disabled={pending}
            icon={<CheckCircle2 className="h-5 w-5" />}
          />
        </div>
      )}
    </div>
  );
}

function SwipeCard({ job }: { job: Job }) {
  const band = job.predicted_salary_band;
  const postingUrl = publicJobUrl(job.source_url);
  return (
    <Card
      variant="glass"
      className="h-full p-6 flex flex-col gap-4 overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <Badge
              variant="outline"
              size="sm"
              className={cn("border", BAND_COLOR[band])}
            >
              <Banknote className="h-3 w-3 mr-1" />
              {formatSalary(job.salary_min, job.salary_max, job.currency, job.salary_period)} · {BAND_LABEL[band]}
            </Badge>
            {job.remote && (
              <Badge variant="outline" size="sm" className="border-cyan-500/40 text-cyan-300">
                <Globe2 className="h-3 w-3 mr-1" /> Remote
              </Badge>
            )}
            <ScoreBadge score={Math.round(job.match_score)} reason={job.rejection_reason} size="sm" />
            <Badge variant="secondary" size="sm">
              {job.source}
            </Badge>
          </div>
          <p className="mb-1 text-xs text-muted-foreground">{JOB_TRACK_LABELS[job.track] ?? job.track} · {job.employment_type ? EMPLOYMENT_LABELS[job.employment_type] : "Contract not stated"}</p>
          <h2 className="text-xl font-semibold leading-tight line-clamp-2">
            <Link href={`/jobs/${job.id}`} className="hover:underline">{job.title}</Link>
          </h2>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Building2 className="h-3 w-3" />
              {job.company}
            </span>
            {job.location && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-3 w-3" />
                {job.location}
              </span>
            )}
            {postingUrl && <a
              href={postingUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[hsl(var(--accent-1))] hover:underline"
            >
              Open <ExternalLink className="h-3 w-3" />
            </a>}
          </div>
        </div>
      </div>

      {/* Key matches */}
      {job.key_matches && job.key_matches.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {job.key_matches.slice(0, 8).map((k) => (
            <span
              key={k}
              className="text-[10px] mono px-2 py-0.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
            >
              {k}
            </span>
          ))}
        </div>
      )}

      {/* Description */}
      <div className="flex-1 overflow-hidden text-xs leading-relaxed text-foreground/85 whitespace-pre-line line-clamp-[16]">
        {job.description?.slice(0, 1400) || "Sin descripción."}
      </div>

      {/* Footer hints */}
      {job.missing_skills && job.missing_skills.length > 0 && (
        <div className="pt-2 border-t border-[hsl(var(--border))] text-[10px] text-muted-foreground">
          <span className="uppercase tracking-wider">Missing: </span>
          {job.missing_skills.slice(0, 6).join(", ")}
        </div>
      )}
    </Card>
  );
}

function Toggle({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border text-[11px] mono transition-colors",
        active
          ? "border-[hsl(var(--accent-1))]/50 bg-[hsl(var(--accent-1))]/10 text-[hsl(var(--accent-1))]"
          : "border-[hsl(var(--border))] text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function BandFilter({
  value,
  onChange,
}: {
  value?: SalaryBand;
  onChange: (v?: SalaryBand) => void;
}) {
  const opts: Array<{ v: SalaryBand | undefined; label: string }> = [
    { v: undefined, label: "Todas" },
    { v: "mid", label: "≥ medio" },
    { v: "high", label: "Solo alto" },
  ];
  return (
    <div className="inline-flex rounded-lg border border-[hsl(var(--border))] p-0.5">
      {opts.map((o) => (
        <button
          key={o.label}
          type="button"
          aria-pressed={value === o.v}
          onClick={() => onChange(o.v)}
          className={cn(
            "px-2.5 py-1 text-[10px] mono rounded-md transition-colors",
            value === o.v
              ? "bg-[hsl(var(--accent-1))]/15 text-[hsl(var(--accent-1))]"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

const COLOR_MAP = {
  rose: "border-rose-500/50 text-rose-300 hover:bg-rose-500/10",
  amber: "border-amber-500/50 text-amber-300 hover:bg-amber-500/10",
  emerald: "border-emerald-500/50 text-emerald-300 hover:bg-emerald-500/10",
} as const;

function ActionBtn({
  onClick,
  color,
  label,
  disabled,
  icon,
}: {
  onClick: () => void;
  color: keyof typeof COLOR_MAP;
  label: string;
  disabled?: boolean;
  icon: React.ReactNode;
}) {
  return (
    <Button
      onClick={onClick}
      disabled={disabled}
      variant="outline"
      className={cn("h-14 px-3 sm:px-6 gap-2 border-2 transition-all", COLOR_MAP[color])}
    >
      {icon}
      <span className="text-sm font-medium">{label}</span>

    </Button>
  );
}
