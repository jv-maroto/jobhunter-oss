"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  COUNTRY_OPTIONS,
  REGION_PRESETS,
  onboardingApi,
  type CvMaster,
  type MergeResult,
} from "@/lib/onboarding";

type Step = "welcome" | "github" | "linkedin" | "cv" | "regions" | "review" | "done";
const ORDER: Step[] = ["welcome", "github", "linkedin", "cv", "regions", "review", "done"];

const STEP_LABELS: Record<Step, string> = {
  welcome: "Bienvenida",
  github: "GitHub",
  linkedin: "LinkedIn",
  cv: "CV",
  regions: "Países",
  review: "Revisión",
  done: "Listo",
};

function emptyCv(): CvMaster {
  return {
    personal: { name: "", email: "", phone: "", location: "", title: "", github: "", linkedin: "", portfolio: "" },
    summary_es: "",
    summary_en: "",
    experience: [],
    education: [],
    certifications: [],
    languages: [],
    skills: {},
    projects: [],
    search_preferences: {},
  };
}

const SOURCE_COLORS: Record<string, string> = {
  github: "text-[hsl(var(--accent-1))] border-[hsl(var(--accent-1))]/40",
  linkedin: "text-sky-400 border-sky-400/40",
  cv: "text-emerald-400 border-emerald-400/40",
  ia: "text-fuchsia-400 border-fuchsia-400/40",
  merged: "text-muted-foreground border-[hsl(var(--border))]",
};

export default function OnboardingPage() {
  const router = useRouter();
  const qc = useQueryClient();

  const [step, setStep] = React.useState<Step>("welcome");
  const [busy, setBusy] = React.useState<string | null>(null);
  const [done, setDone] = React.useState<Record<string, boolean>>({});

  const [githubUser, setGithubUser] = React.useState("");
  const [regionPreset, setRegionPreset] = React.useState<string | null>("only_spain");
  const [customRegions, setCustomRegions] = React.useState<string[]>([]);

  const [merge, setMerge] = React.useState<MergeResult | null>(null);
  const [cv, setCv] = React.useState<CvMaster | null>(null);
  const [rawOpen, setRawOpen] = React.useState(false);

  const idx = ORDER.indexOf(step);
  const goTo = (s: Step) => setStep(s);
  const next = () => setStep(ORDER[Math.min(idx + 1, ORDER.length - 1)]);
  const back = () => setStep(ORDER[Math.max(idx - 1, 0)]);

  // ---- acciones de ingesta ----
  async function connectGithub() {
    if (!githubUser.trim()) return;
    setBusy("github");
    try {
      await onboardingApi.github(githubUser.trim());
      setDone((d) => ({ ...d, github: true }));
      toast.success("GitHub importado");
      next();
    } catch {
      toast.error("No se pudo importar GitHub (¿usuario correcto?)");
    } finally {
      setBusy(null);
    }
  }

  async function uploadFile(kind: "cv" | "linkedin", file: File) {
    setBusy(kind);
    try {
      const res =
        kind === "cv" ? await onboardingApi.uploadCv(file) : await onboardingApi.uploadLinkedin(file);
      setDone((d) => ({ ...d, [kind]: true }));
      const warns = res.warnings ?? [];
      if (warns.length) toast.warning(warns[0]);
      else toast.success(kind === "cv" ? "CV analizado" : "LinkedIn importado");
      next();
    } catch {
      toast.error("No se pudo procesar el archivo");
    } finally {
      setBusy(null);
    }
  }

  // ---- fusión al entrar en revisión ----
  const runMerge = React.useCallback(async () => {
    setBusy("merge");
    try {
      const res = await onboardingApi.merge();
      setMerge(res);
      setCv(res.cv_master);
    } catch {
      // Sin fragmentos (todo omitido) -> perfil vacío para rellenar a mano.
      setMerge({ cv_master: emptyCv(), field_sources: {}, conflicts: [], llm_used: false });
      setCv(emptyCv());
    } finally {
      setBusy(null);
    }
  }, []);

  React.useEffect(() => {
    if (step === "review" && !merge) void runMerge();
  }, [step, merge, runMerge]);

  function patchPersonal(key: string, value: string) {
    setCv((c) => (c ? { ...c, personal: { ...(c.personal ?? {}), [key]: value } } : c));
  }

  async function saveProfile() {
    if (!cv) return;
    if (!cv.personal?.name?.trim()) {
      toast.error("El nombre es obligatorio");
      return;
    }
    const regions = regionPreset
      ? REGION_PRESETS.find((p) => p.id === regionPreset)?.regions ?? []
      : customRegions;
    const finalCv: CvMaster = {
      ...cv,
      search_preferences: {
        ...(cv.search_preferences ?? {}),
        region_preset: regionPreset ?? "custom",
        regions,
        queries_auto: true,
      },
    };
    setBusy("complete");
    try {
      await onboardingApi.complete(finalCv);
      await qc.invalidateQueries({ queryKey: ["onboarding", "status"] });
      setStep("done");
    } catch {
      toast.error("No se pudo guardar el perfil");
    } finally {
      setBusy(null);
    }
  }

  function toggleCountry(iso: string) {
    setRegionPreset(null);
    setCustomRegions((r) => (r.includes(iso) ? r.filter((x) => x !== iso) : [...r, iso]));
  }

  return (
    <div className="fixed inset-0 z-[100] overflow-y-auto bg-[hsl(var(--background))]/95 backdrop-blur-xl">
      <div className="mx-auto flex min-h-full max-w-2xl flex-col gap-6 px-5 py-10">
        <Stepper step={step} />

        {step === "welcome" && (
          <WelcomeStep
            onStart={() => goTo("github")}
            onManual={async () => {
              goTo("regions");
            }}
          />
        )}

        {step === "github" && (
          <StepCard
            title="Conecta tu GitHub"
            description="Analizamos tus repos públicos para extraer skills y proyectos destacados. Opcional."
            onBack={back}
            onSkip={next}
            done={done.github}
          >
            <div className="flex gap-2">
              <Input
                placeholder="usuario o https://github.com/usuario"
                value={githubUser}
                onChange={(e) => setGithubUser(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && connectGithub()}
              />
              <Button onClick={connectGithub} disabled={busy === "github" || !githubUser.trim()}>
                {busy === "github" ? "Importando…" : "Importar"}
              </Button>
            </div>
          </StepCard>
        )}

        {step === "linkedin" && (
          <StepCard
            title="Importa tu LinkedIn"
            description="Sube el .zip del export oficial («Get a copy of your data») o el PDF de tu perfil. Sin riesgo de baneo."
            onBack={back}
            onSkip={next}
            done={done.linkedin}
          >
            <FileDrop
              accept=".zip,.pdf"
              busy={busy === "linkedin"}
              label="Arrastra tu .zip o .pdf de LinkedIn"
              onFile={(f) => uploadFile("linkedin", f)}
            />
            <p className="mt-2 text-xs text-muted-foreground">
              En LinkedIn: Ajustes → Privacidad de datos → Obtén una copia de tus datos → «el archivo
              mayor» (incluye experiencia y skills).
            </p>
          </StepCard>
        )}

        {step === "cv" && (
          <StepCard
            title="Sube tu CV"
            description="PDF, DOCX o TXT. Lo analizamos con IA para estructurar tu experiencia. Opcional."
            onBack={back}
            onSkip={next}
            done={done.cv}
          >
            <FileDrop
              accept=".pdf,.docx,.txt"
              busy={busy === "cv"}
              label="Arrastra tu CV (.pdf / .docx / .txt)"
              onFile={(f) => uploadFile("cv", f)}
            />
          </StepCard>
        )}

        {step === "regions" && (
          <StepCard
            title="¿Dónde quieres buscar trabajo?"
            description="Activamos las plataformas relevantes a los países que elijas."
            onBack={back}
            onNext={() => goTo("review")}
            nextLabel="Generar perfil"
          >
            <div className="flex flex-wrap gap-2">
              {REGION_PRESETS.map((p) => (
                <Chip
                  key={p.id}
                  active={regionPreset === p.id}
                  onClick={() => {
                    setRegionPreset(p.id);
                    setCustomRegions([]);
                  }}
                >
                  {p.label}
                </Chip>
              ))}
            </div>
            <div className="mt-4">
              <p className="mb-2 text-xs text-muted-foreground">O elige países concretos:</p>
              <div className="flex flex-wrap gap-2">
                {COUNTRY_OPTIONS.map((c) => (
                  <Chip key={c.iso} active={customRegions.includes(c.iso)} onClick={() => toggleCountry(c.iso)}>
                    {c.label}
                  </Chip>
                ))}
              </div>
            </div>
          </StepCard>
        )}

        {step === "review" && (
          <ReviewStep
            busy={busy}
            cv={cv}
            merge={merge}
            rawOpen={rawOpen}
            setRawOpen={setRawOpen}
            onBack={back}
            onPatchPersonal={patchPersonal}
            onPatchField={(k, v) => setCv((c) => (c ? { ...c, [k]: v } : c))}
            onSetCv={setCv}
            onSave={saveProfile}
          />
        )}

        {step === "done" && (
          <Card variant="solid">
            <CardHeader>
              <CardTitle>¡Perfil creado! 🎉</CardTitle>
              <CardDescription>
                Tu cv_master.json ya está listo. Puedes ajustarlo cuando quieras en Ajustes.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                variant="solid"
                onClick={() => {
                  qc.invalidateQueries();
                  router.replace("/today");
                }}
              >
                Ir al dashboard
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

// ---------------- subcomponentes ----------------

function Stepper({ step }: { step: Step }) {
  const idx = ORDER.indexOf(step);
  return (
    <div className="flex items-center justify-between gap-1">
      {ORDER.map((s, i) => (
        <div key={s} className="flex flex-1 flex-col items-center gap-1.5">
          <div
            className={cn(
              "h-1 w-full rounded-full transition-colors",
              i <= idx ? "bg-[hsl(var(--accent-1))]" : "bg-white/10",
            )}
          />
          <span className={cn("text-[10px]", i === idx ? "text-foreground" : "text-muted-foreground")}>
            {STEP_LABELS[s]}
          </span>
        </div>
      ))}
    </div>
  );
}

function WelcomeStep({ onStart, onManual }: { onStart: () => void; onManual: () => void }) {
  return (
    <Card variant="solid">
      <CardHeader>
        <CardTitle>Bienvenido a JobHunter</CardTitle>
        <CardDescription>
          Todo corre en tu máquina (local-first, sin nube). Vamos a construir tu perfil a partir de tu
          GitHub, LinkedIn y CV. Nada se guarda sin que lo revises.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Button variant="solid" size="lg" onClick={onStart}>
          Empezar
        </Button>
        <button className="text-xs text-muted-foreground hover:text-foreground" onClick={onManual}>
          Prefiero rellenarlo a mano
        </button>
      </CardContent>
    </Card>
  );
}

function StepCard({
  title,
  description,
  children,
  onBack,
  onNext,
  onSkip,
  nextLabel = "Siguiente",
  done,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
  onBack?: () => void;
  onNext?: () => void;
  onSkip?: () => void;
  nextLabel?: string;
  done?: boolean;
}) {
  return (
    <Card variant="solid">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {title}
          {done && <span className="text-xs text-emerald-400">✓ importado</span>}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        {children}
        <div className="mt-5 flex items-center justify-between">
          <Button variant="ghost" onClick={onBack} disabled={!onBack}>
            Atrás
          </Button>
          <div className="flex gap-2">
            {onSkip && (
              <Button variant="ghost" onClick={onSkip}>
                Omitir
              </Button>
            )}
            {onNext && (
              <Button variant="solid" onClick={onNext}>
                {nextLabel}
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function Chip({
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
        "rounded-full border px-3 py-1.5 text-sm transition-colors",
        active
          ? "border-[hsl(var(--accent-1))]/55 bg-[hsl(var(--accent-1))]/15 text-[hsl(var(--accent-1))]"
          : "border-[hsl(var(--border))] text-muted-foreground hover:text-foreground hover:border-[hsl(var(--accent-1))]/40",
      )}
    >
      {children}
    </button>
  );
}

function FileDrop({
  accept,
  label,
  busy,
  onFile,
}: {
  accept: string;
  label: string;
  busy: boolean;
  onFile: (f: File) => void;
}) {
  const [drag, setDrag] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      onClick={() => inputRef.current?.click()}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-8 text-center text-sm transition-colors",
        drag
          ? "border-[hsl(var(--accent-1))]/60 bg-[hsl(var(--accent-1))]/10"
          : "border-[hsl(var(--border-strong))] hover:border-[hsl(var(--accent-1))]/40",
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
        }}
      />
      <span className="text-muted-foreground">{busy ? "Procesando…" : label}</span>
    </div>
  );
}

function SourceBadge({ source }: { source?: string }) {
  if (!source) return null;
  return (
    <span
      className={cn(
        "ml-2 rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wide",
        SOURCE_COLORS[source] ?? SOURCE_COLORS.merged,
      )}
    >
      {source}
    </span>
  );
}

function ReviewStep({
  busy,
  cv,
  merge,
  rawOpen,
  setRawOpen,
  onBack,
  onPatchPersonal,
  onPatchField,
  onSetCv,
  onSave,
}: {
  busy: string | null;
  cv: CvMaster | null;
  merge: MergeResult | null;
  rawOpen: boolean;
  setRawOpen: (b: boolean) => void;
  onBack: () => void;
  onPatchPersonal: (k: string, v: string) => void;
  onPatchField: (k: string, v: string) => void;
  onSetCv: (c: CvMaster) => void;
  onSave: () => void;
}) {
  if (busy === "merge" || !cv) {
    return (
      <Card variant="solid">
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Fusionando tu perfil…
        </CardContent>
      </Card>
    );
  }

  const fs = merge?.field_sources ?? {};
  const p = cv.personal ?? {};
  const skills = cv.skills ?? {};
  const allSkills = Object.values(skills).flat();

  const PERSONAL_FIELDS: { key: string; label: string }[] = [
    { key: "name", label: "Nombre" },
    { key: "title", label: "Título profesional" },
    { key: "email", label: "Email" },
    { key: "phone", label: "Teléfono" },
    { key: "location", label: "Ubicación" },
    { key: "github", label: "GitHub" },
    { key: "linkedin", label: "LinkedIn" },
    { key: "portfolio", label: "Portfolio" },
  ];

  return (
    <Card variant="solid">
      <CardHeader>
        <CardTitle>Revisa tu perfil</CardTitle>
        <CardDescription>
          Lo generamos a partir de tus fuentes. Edita lo que quieras antes de guardar — nada se ha
          escrito todavía.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {merge && merge.conflicts.length > 0 && (
          <div className="rounded-md border border-[hsl(var(--accent-warn))]/40 bg-[hsl(var(--accent-warn))]/10 p-3 text-xs">
            <p className="mb-1 font-medium text-[hsl(var(--accent-warn))]">
              {merge.conflicts.length} dato(s) con discrepancias entre fuentes:
            </p>
            <ul className="space-y-0.5 text-muted-foreground">
              {merge.conflicts.slice(0, 5).map((c, i) => (
                <li key={i}>
                  <code>{c.field}</code>: usamos «{String(c.kept)}» ({c.kept_source}) en vez de «
                  {String(c.other)}» ({c.other_source})
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {PERSONAL_FIELDS.map((f) => (
            <label key={f.key} className="flex flex-col gap-1 text-xs">
              <span className="flex items-center text-muted-foreground">
                {f.label}
                <SourceBadge source={fs[`personal.${f.key}`]} />
              </span>
              <Input
                value={String(p[f.key] ?? "")}
                onChange={(e) => onPatchPersonal(f.key, e.target.value)}
              />
            </label>
          ))}
        </div>

        <label className="flex flex-col gap-1 text-xs">
          <span className="flex items-center text-muted-foreground">
            Resumen (ES)
            <SourceBadge source={fs.summary_es} />
          </span>
          <Textarea
            rows={3}
            value={cv.summary_es ?? ""}
            onChange={(e) => onPatchField("summary_es", e.target.value)}
          />
        </label>

        <div className="grid grid-cols-3 gap-3 text-center text-xs">
          <Stat n={cv.experience?.length ?? 0} label="Experiencias" />
          <Stat n={allSkills.length} label="Skills" />
          <Stat n={cv.projects?.length ?? 0} label="Proyectos" />
        </div>

        {allSkills.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {allSkills.slice(0, 24).map((s, i) => (
              <span key={i} className="rounded bg-white/5 px-2 py-0.5 text-[11px] text-muted-foreground">
                {s}
              </span>
            ))}
          </div>
        )}

        <details open={rawOpen} onToggle={(e) => setRawOpen((e.target as HTMLDetailsElement).open)}>
          <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
            Editar JSON completo (avanzado)
          </summary>
          <Textarea
            className="mt-2 font-mono text-[11px]"
            rows={12}
            defaultValue={JSON.stringify(cv, null, 2)}
            onBlur={(e) => {
              try {
                onSetCv(JSON.parse(e.target.value));
                toast.success("JSON aplicado");
              } catch {
                toast.error("JSON inválido, no aplicado");
              }
            }}
          />
        </details>

        <div className="flex items-center justify-between">
          <Button variant="ghost" onClick={onBack}>
            Atrás
          </Button>
          <Button variant="solid" onClick={onSave} disabled={busy === "complete"}>
            {busy === "complete" ? "Guardando…" : "Guardar perfil"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function Stat({ n, label }: { n: number; label: string }) {
  return (
    <div className="rounded-md border border-[hsl(var(--border))] py-2">
      <div className="text-lg font-semibold text-foreground">{n}</div>
      <div className="text-[10px] text-muted-foreground">{label}</div>
    </div>
  );
}
