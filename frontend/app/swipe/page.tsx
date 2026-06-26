"use client";

import * as React from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Banknote,
  Building2,
  CheckCircle2,
  ExternalLink,
  FileText,
  Globe2,
  MapPin,
  Star,
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
import type { Job, JobTrack, SalaryBand } from "@/lib/types";
import { cn } from "@/lib/utils";

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

function formatSalary(j: Job): string {
  if (!j.salary_min && !j.salary_max) return "Sin rango";
  const cur = j.currency || "EUR";
  const sym = cur === "USD" ? "$" : cur === "GBP" ? "£" : "€";
  const fmt = (n?: number) => (n ? `${Math.round(n / 1000)}k` : "?");
  if (j.salary_min && j.salary_max) return `${sym}${fmt(j.salary_min)}–${fmt(j.salary_max)}`;
  return `${sym}${fmt(j.salary_max ?? j.salary_min)}`;
}

export default function SwipePage() {
  const [track, setTrack] = React.useState<JobTrack>("dev");
  const [remoteOnly, setRemoteOnly] = React.useState(false);
  const [minBand, setMinBand] = React.useState<SalaryBand | undefined>(undefined);
  const [index, setIndex] = React.useState(0);
  const [direction, setDirection] = React.useState<-1 | 0 | 1>(0);

  const query = useSwipeJobs({
    track,
    remote_only: remoteOnly,
    min_band: minBand,
  });
  const prepare = usePrepareApplication();
  const updateStatus = useUpdateJobStatus();

  React.useEffect(() => {
    setIndex(0);
  }, [track, remoteOnly, minBand]);

  const jobs = query.data ?? [];
  const current = jobs[index];
  const next = jobs[index + 1];

  const advance = (dir: -1 | 1) => {
    setDirection(dir);
    setIndex((i) => i + 1);
  };

  const onSkip = async () => {
    if (!current) return;
    try {
      await updateStatus.mutateAsync({
        id: current.id,
        status: "rejected",
        notes: "Skipped from swipe",
      });
    } catch {
      /* noop */
    }
    advance(-1);
  };

  const onSave = () => {
    if (!current) return;
    toast.success("Guardado", { icon: <Star className="h-4 w-4" /> });
    advance(1);
  };

  const onPrepare = async () => {
    if (!current) return;
    try {
      toast.loading("Generando CV + cover…", { id: `prep-${current.id}` });
      await prepare.mutateAsync(current.id);
      toast.success("CV + cover listos", {
        id: `prep-${current.id}`,
        icon: <FileText className="h-4 w-4" />,
      });
    } catch (e) {
      toast.error("Fallo al preparar", {
        id: `prep-${current.id}`,
        description: String(e).slice(0, 120),
      });
    }
    advance(1);
  };

  return (
    <div className="space-y-5">
      {/* Track tabs */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="inline-flex rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--surface))]/60 p-1">
          <TabButton active={track === "dev"} onClick={() => setTrack("dev")}>
            Dev / Full-Stack · AI
          </TabButton>
          <TabButton
            active={track === "sysadmin"}
            onClick={() => setTrack("sysadmin")}
          >
            SysAdmin · DevOps
          </TabButton>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Toggle active={remoteOnly} onClick={() => setRemoteOnly((v) => !v)}>
            <Globe2 className="h-3.5 w-3.5" /> Solo remoto
          </Toggle>
          <BandFilter value={minBand} onChange={setMinBand} />
          <span className="text-[11px] text-muted-foreground mono">
            {jobs.length > 0
              ? `${Math.min(index + 1, jobs.length)} / ${jobs.length}`
              : "—"}
          </span>
        </div>
      </div>

      {/* Card stack */}
      <div className="relative mx-auto max-w-2xl h-[520px]">
        {query.isLoading && <Skeleton className="absolute inset-0 rounded-2xl" />}

        {!query.isLoading && jobs.length === 0 && (
          <div className="absolute inset-0 grid place-items-center text-center text-muted-foreground">
            <div>
              <p className="text-sm">No quedan ofertas pendientes en este filtro.</p>
              <p className="text-xs mt-1">
                Lanza scraping desde Jobs o cambia los filtros.
              </p>
            </div>
          </div>
        )}

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
        <div className="flex items-center justify-center gap-4">
          <ActionBtn
            onClick={onSkip}
            color="rose"
            label="Skip"
            kbd="←"
            icon={<X className="h-5 w-5" />}
          />
          <ActionBtn
            onClick={onSave}
            color="amber"
            label="Save"
            kbd="↑"
            icon={<Star className="h-5 w-5" />}
          />
          <ActionBtn
            onClick={onPrepare}
            color="emerald"
            label="Preparar"
            kbd="→"
            icon={<CheckCircle2 className="h-5 w-5" />}
          />
        </div>
      )}
    </div>
  );
}

function SwipeCard({ job }: { job: Job }) {
  const band = job.predicted_salary_band;
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
              {formatSalary(job)} · {BAND_LABEL[band]}
            </Badge>
            {job.remote && (
              <Badge variant="outline" size="sm" className="border-cyan-500/40 text-cyan-300">
                <Globe2 className="h-3 w-3 mr-1" /> Remote
              </Badge>
            )}
            <Badge variant="mono" size="sm">
              score {Math.round(job.match_score)}
            </Badge>
            <Badge variant="secondary" size="sm">
              {job.source}
            </Badge>
          </div>
          <h2 className="text-xl font-semibold leading-tight line-clamp-2">
            {job.title}
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
            <a
              href={job.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[hsl(var(--accent-1))] hover:underline"
            >
              Open <ExternalLink className="h-3 w-3" />
            </a>
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

function TabButton({
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
      onClick={onClick}
      className={cn(
        "px-4 py-2 text-xs font-medium rounded-lg transition-colors",
        active
          ? "bg-[hsl(var(--accent-1))]/15 text-[hsl(var(--accent-1))] border border-[hsl(var(--accent-1))]/40"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
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
  kbd,
  icon,
}: {
  onClick: () => void;
  color: keyof typeof COLOR_MAP;
  label: string;
  kbd?: string;
  icon: React.ReactNode;
}) {
  return (
    <Button
      onClick={onClick}
      variant="outline"
      className={cn("h-14 px-6 gap-2 border-2 transition-all", COLOR_MAP[color])}
    >
      {icon}
      <span className="text-sm font-medium">{label}</span>
      {kbd && (
        <span className="text-[10px] opacity-60 mono ml-1 border rounded px-1 py-0.5">
          {kbd}
        </span>
      )}
    </Button>
  );
}
