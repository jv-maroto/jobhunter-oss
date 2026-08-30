"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { LanguageToggle, useLang } from "@/lib/i18n";
import {
  COUNTRY_OPTIONS,
  REGION_PRESETS,
  onboardingApi,
  type CvMaster,
  type MergeResult,
  type RoleSuggestion,
} from "@/lib/onboarding";
import {
  AI_PROVIDERS,
  aiSettingsApi,
  type AiMode,
  type AiProvider,
  type AiSettingsPatch,
} from "@/lib/aiSettings";

type Step = "welcome" | "ai" | "github" | "linkedin" | "cv" | "regions" | "roles" | "review" | "done";
const ORDER: Step[] = ["welcome", "ai", "github", "linkedin", "cv", "regions", "roles", "review", "done"];

const PRESET_T: Record<string, string> = {
  only_spain: "rg_preset_es",
  all_europe: "rg_preset_eu",
  remote_worldwide: "rg_preset_remote",
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
  const { t } = useLang();

  const [step, setStep] = React.useState<Step>("welcome");
  const [busy, setBusy] = React.useState<string | null>(null);
  const [done, setDone] = React.useState<Record<string, boolean>>({});

  const [githubUser, setGithubUser] = React.useState("");
  const [liText, setLiText] = React.useState("");
  const [regionPreset, setRegionPreset] = React.useState<string | null>("only_spain");
  const [customRegions, setCustomRegions] = React.useState<string[]>([]);

  // Paso IA: elegir local (Ollama) / cloud (con clave) / sin IA.
  const [aiMode, setAiMode] = React.useState<AiMode>("local");
  const [aiProvider, setAiProvider] = React.useState<AiProvider>("anthropic");
  const [aiKey, setAiKey] = React.useState("");
  const [aiLocalOk, setAiLocalOk] = React.useState(true);
  // Ollama responde pero el modelo no esta descargado -> aviso con el `ollama pull`.
  const [aiLocalModel, setAiLocalModel] = React.useState<{ name: string; server: boolean; ok: boolean }>({
    name: "",
    server: true,
    ok: true,
  });
  const [aiSeeded, setAiSeeded] = React.useState(false);

  // Paso ROLES: sugerencias de IA + selección multi-chip + roles propios.
  const [roleSuggestions, setRoleSuggestions] = React.useState<RoleSuggestion[] | null>(null);
  const [extraRoles, setExtraRoles] = React.useState<string[]>([]);
  const [selectedRoles, setSelectedRoles] = React.useState<string[]>([]);
  const [customRole, setCustomRole] = React.useState("");

  const [merge, setMerge] = React.useState<MergeResult | null>(null);
  const [cv, setCv] = React.useState<CvMaster | null>(null);
  const [rawOpen, setRawOpen] = React.useState(false);

  const idx = ORDER.indexOf(step);
  const goTo = (s: Step) => setStep(s);
  const next = () => setStep(ORDER[Math.min(idx + 1, ORDER.length - 1)]);
  const back = () => setStep(ORDER[Math.max(idx - 1, 0)]);

  async function connectGithub() {
    if (!githubUser.trim()) return;
    setBusy("github");
    try {
      await onboardingApi.github(githubUser.trim());
      setDone((d) => ({ ...d, github: true }));
      toast.success(t("t_gh_ok"));
      next();
    } catch {
      toast.error(t("t_gh_err"));
    } finally {
      setBusy(null);
    }
  }

  async function pasteLinkedin() {
    if (!liText.trim()) {
      toast.error(t("t_text_empty"));
      return;
    }
    setBusy("li-paste");
    try {
      await onboardingApi.linkedinPaste(liText.trim());
      setDone((d) => ({ ...d, linkedin: true }));
      toast.success(t("t_li_ok"));
      next();
    } catch {
      toast.error(t("t_file_err"));
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
      else toast.success(kind === "cv" ? t("t_cv_ok") : t("t_li_ok"));
      next();
    } catch {
      toast.error(t("t_file_err"));
    } finally {
      setBusy(null);
    }
  }

  const runMerge = React.useCallback(async () => {
    setBusy("merge");
    try {
      const res = await onboardingApi.merge();
      setMerge(res);
      setCv(res.cv_master);
    } catch {
      setMerge({ cv_master: emptyCv(), field_sources: {}, conflicts: [], llm_used: false });
      setCv(emptyCv());
    } finally {
      setBusy(null);
    }
  }, []);

  React.useEffect(() => {
    if (step === "review" && !merge) void runMerge();
  }, [step, merge, runMerge]);

  const loadRoles = React.useCallback(async () => {
    setBusy("roles");
    try {
      const res = await onboardingApi.suggestRoles();
      const roles = res.roles ?? [];
      setRoleSuggestions(roles);
      // Pre-seleccionamos todas las sugerencias; el usuario quita las que no encajen.
      setSelectedRoles((cur) => (cur.length ? cur : roles.map((r) => r.label)));
    } catch {
      setRoleSuggestions([]); // sin IA/backend: el usuario añade los suyos a mano
    } finally {
      setBusy(null);
    }
  }, []);

  React.useEffect(() => {
    if (step === "roles" && roleSuggestions === null && busy !== "roles") void loadRoles();
  }, [step, roleSuggestions, busy, loadRoles]);

  const toggleRole = (label: string) =>
    setSelectedRoles((r) => (r.includes(label) ? r.filter((x) => x !== label) : [...r, label]));

  function addCustomRole() {
    const label = customRole.trim();
    if (!label) return;
    if (!extraRoles.includes(label) && !(roleSuggestions ?? []).some((r) => r.label === label)) {
      setExtraRoles((r) => [...r, label]);
    }
    setSelectedRoles((r) => (r.includes(label) ? r : [...r, label]));
    setCustomRole("");
  }

  // Carga/siembra el estado de IA al entrar en el paso (una sola vez).
  const loadAi = React.useCallback(async () => {
    try {
      const s = await aiSettingsApi.get();
      const localOk = s.local_available && s.local_model_available;
      setAiLocalOk(localOk);
      setAiLocalModel({ name: s.local_model, server: s.local_available, ok: s.local_model_available });
      setAiProvider(s.ai_cloud_provider);
      if (s.has_key.anthropic || s.has_key.openai || s.has_key.gemini) setAiMode("cloud");
      else if (localOk) setAiMode("local");
      else setAiMode("off");
    } catch {
      /* backend offline: dejamos los defaults */
    } finally {
      setAiSeeded(true);
    }
  }, []);

  React.useEffect(() => {
    if (step === "ai" && !aiSeeded) void loadAi();
  }, [step, aiSeeded, loadAi]);

  async function saveAi() {
    setBusy("ai");
    try {
      const patch: AiSettingsPatch = { ai_mode: aiMode };
      if (aiMode === "cloud") {
        patch.ai_cloud_provider = aiProvider;
        if (aiKey.trim()) patch.keys = { [aiProvider]: aiKey.trim() };
      }
      await aiSettingsApi.update(patch);
      toast.success(t("t_ai_saved"));
      next();
    } catch {
      toast.error(t("t_ai_err"));
    } finally {
      setBusy(null);
    }
  }

  function patchPersonal(key: string, value: string) {
    setCv((c) => (c ? { ...c, personal: { ...(c.personal ?? {}), [key]: value } } : c));
  }

  async function saveProfile() {
    if (!cv) return;
    if (!cv.personal?.name?.trim()) {
      toast.error(t("t_name_req"));
      return;
    }
    const regions = regionPreset
      ? REGION_PRESETS.find((p) => p.id === regionPreset)?.regions ?? []
      : customRegions;
    if (regions.length === 0) {
      toast.error(t("t_region_req"));
      return;
    }
    const finalCv: CvMaster = {
      ...cv,
      search_preferences: {
        ...(cv.search_preferences ?? {}),
        region_preset: regionPreset ?? "custom",
        regions: [...regions],
        roles: [...selectedRoles],
        queries_auto: true,
      },
    };
    setBusy("complete");
    try {
      await onboardingApi.complete(finalCv);
      await qc.invalidateQueries({ queryKey: ["onboarding", "status"] });
      setStep("done");
    } catch {
      toast.error(t("t_saved_err"));
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
        <div className="flex items-center justify-between gap-3">
          <Stepper step={step} />
          <LanguageToggle />
        </div>

        {step === "welcome" && (
          <WelcomeStep onStart={() => goTo("ai")} onManual={() => goTo("ai")} />
        )}

        {step === "ai" && (
          <StepCard
            title={t("ai_title")}
            description={t("ai_desc")}
            onBack={back}
            onNext={saveAi}
            nextLabel={busy === "ai" ? t("saving") : t("ai_continue")}
          >
            <div className="flex flex-col gap-2">
              <AiModeOption
                active={aiMode === "local"}
                disabled={!aiLocalOk}
                title={t("ai_local")}
                desc={
                  aiLocalOk
                    ? t("ai_local_desc")
                    : aiLocalModel.server
                      ? t("ai_local_model_missing").replaceAll("{model}", aiLocalModel.name)
                      : t("ai_local_unavailable")
                }
                onClick={() => aiLocalOk && setAiMode("local")}
              />
              <AiModeOption
                active={aiMode === "cloud"}
                title={t("ai_cloud")}
                desc={t("ai_cloud_desc")}
                onClick={() => setAiMode("cloud")}
              />
              <AiModeOption
                active={aiMode === "off"}
                title={t("ai_off")}
                desc={t("ai_off_desc")}
                onClick={() => setAiMode("off")}
              />
            </div>
            {aiMode === "cloud" && (
              <div className="mt-3 flex flex-col gap-2">
                <div className="flex flex-wrap gap-2">
                  {AI_PROVIDERS.map((p) => (
                    <Chip
                      key={p.id}
                      active={aiProvider === p.id}
                      onClick={() => setAiProvider(p.id)}
                    >
                      {p.label}
                    </Chip>
                  ))}
                </div>
                <Input
                  type="password"
                  placeholder={
                    AI_PROVIDERS.find((p) => p.id === aiProvider)?.keyPlaceholder ?? "API key"
                  }
                  value={aiKey}
                  onChange={(e) => setAiKey(e.target.value)}
                />
              </div>
            )}
          </StepCard>
        )}

        {step === "github" && (
          <StepCard
            title={t("gh_title")}
            description={t("gh_desc")}
            onBack={back}
            onSkip={next}
            done={done.github}
          >
            <div className="flex gap-2">
              <Input
                placeholder={t("gh_ph")}
                value={githubUser}
                onChange={(e) => setGithubUser(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && connectGithub()}
              />
              <Button onClick={connectGithub} disabled={busy === "github" || !githubUser.trim()}>
                {busy === "github" ? t("importing") : t("import")}
              </Button>
            </div>
          </StepCard>
        )}

        {step === "linkedin" && (
          <StepCard
            title={t("li_title")}
            description={t("li_desc")}
            onBack={back}
            onSkip={next}
            done={done.linkedin}
          >
            <label className="mb-1 block text-xs text-muted-foreground">{t("li_paste_label")}</label>
            <Textarea
              rows={5}
              placeholder={t("li_paste_ph")}
              value={liText}
              onChange={(e) => setLiText(e.target.value)}
            />
            <Button
              className="mt-2"
              onClick={pasteLinkedin}
              disabled={busy === "li-paste" || !liText.trim()}
            >
              {busy === "li-paste" ? t("processing") : t("li_paste_btn")}
            </Button>

            <p className="mt-4 mb-1 text-xs text-muted-foreground">{t("li_or_upload")}</p>
            <FileDrop
              accept=".zip,.pdf"
              busy={busy === "linkedin"}
              label=".zip / .pdf"
              onFile={(f) => uploadFile("linkedin", f)}
            />
            <p className="mt-2 text-[11px] text-muted-foreground">{t("li_ext_note")}</p>
          </StepCard>
        )}

        {step === "cv" && (
          <StepCard
            title={t("cv_title")}
            description={t("cv_desc")}
            onBack={back}
            onSkip={next}
            done={done.cv}
          >
            <FileDrop
              accept=".pdf,.docx,.txt"
              busy={busy === "cv"}
              label={t("cv_drop")}
              onFile={(f) => uploadFile("cv", f)}
            />
          </StepCard>
        )}

        {step === "regions" && (
          <StepCard
            title={t("rg_title")}
            description={t("rg_desc")}
            onBack={back}
            onNext={() => goTo("roles")}
            nextLabel={t("next")}
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
                  {t(PRESET_T[p.id] ?? p.id)}
                </Chip>
              ))}
            </div>
            <div className="mt-4">
              <p className="mb-2 text-xs text-muted-foreground">{t("rg_or_countries")}</p>
              <div className="flex flex-wrap gap-2">
                {COUNTRY_OPTIONS.map((c) => (
                  <Chip key={c.iso} active={customRegions.includes(c.iso)} onClick={() => toggleCountry(c.iso)}>
                    {t(`c_${c.iso}`)}
                  </Chip>
                ))}
              </div>
            </div>
          </StepCard>
        )}

        {step === "roles" && (
          <StepCard
            title={t("roles_title")}
            description={t("roles_desc")}
            onBack={back}
            onNext={() => goTo("review")}
            nextLabel={t("generate")}
          >
            {busy === "roles" ? (
              <p className="py-6 text-center text-sm text-muted-foreground">{t("roles_loading")}</p>
            ) : (
              <>
                {(roleSuggestions ?? []).length === 0 && extraRoles.length === 0 && (
                  <p className="mb-3 text-xs text-muted-foreground">{t("roles_empty")}</p>
                )}
                <div className="flex flex-wrap gap-2">
                  {(roleSuggestions ?? []).map((r) => (
                    <Chip
                      key={r.id}
                      active={selectedRoles.includes(r.label)}
                      onClick={() => toggleRole(r.label)}
                      title={r.why}
                    >
                      {r.label}
                    </Chip>
                  ))}
                  {extraRoles.map((label) => (
                    <Chip
                      key={`x:${label}`}
                      active={selectedRoles.includes(label)}
                      onClick={() => toggleRole(label)}
                    >
                      {label}
                    </Chip>
                  ))}
                </div>

                <div className="mt-4 flex gap-2">
                  <Input
                    placeholder={t("roles_add_ph")}
                    value={customRole}
                    onChange={(e) => setCustomRole(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addCustomRole();
                      }
                    }}
                  />
                  <Button variant="outline" onClick={addCustomRole} disabled={!customRole.trim()}>
                    {t("roles_add_btn")}
                  </Button>
                </div>

                <p className="mt-3 text-[11px] text-muted-foreground">
                  {selectedRoles.length} {t("roles_selected")}
                </p>
              </>
            )}
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
              <CardTitle>{t("done_title")}</CardTitle>
              <CardDescription>{t("done_desc")}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                variant="solid"
                onClick={() => {
                  qc.invalidateQueries();
                  router.replace("/today");
                }}
              >
                {t("go_dashboard")}
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
  const { t } = useLang();
  const idx = ORDER.indexOf(step);
  return (
    <div className="flex flex-1 items-center justify-between gap-1">
      {ORDER.map((s, i) => (
        <div key={s} className="flex flex-1 flex-col items-center gap-1.5">
          <div
            className={cn(
              "h-1 w-full rounded-full transition-colors",
              i <= idx ? "bg-[hsl(var(--accent-1))]" : "bg-white/10",
            )}
          />
          <span className={cn("text-[10px]", i === idx ? "text-foreground" : "text-muted-foreground")}>
            {t(`step_${s}`)}
          </span>
        </div>
      ))}
    </div>
  );
}

function WelcomeStep({ onStart, onManual }: { onStart: () => void; onManual: () => void }) {
  const { t } = useLang();
  return (
    <Card variant="solid">
      <CardHeader>
        <CardTitle>{t("welcome_title")}</CardTitle>
        <CardDescription>{t("welcome_desc")}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Button variant="solid" size="lg" onClick={onStart}>
          {t("start")}
        </Button>
        <button className="text-xs text-muted-foreground hover:text-foreground" onClick={onManual}>
          {t("manual")}
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
  nextLabel,
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
  const { t } = useLang();
  return (
    <Card variant="solid">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {title}
          {done && <span className="text-xs text-emerald-400">{t("imported")}</span>}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        {children}
        <div className="mt-5 flex items-center justify-between">
          <Button variant="ghost" onClick={onBack} disabled={!onBack}>
            {t("back")}
          </Button>
          <div className="flex gap-2">
            {onSkip && (
              <Button variant="ghost" onClick={onSkip}>
                {t("skip")}
              </Button>
            )}
            {onNext && (
              <Button variant="solid" onClick={onNext}>
                {nextLabel ?? t("next")}
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
  title,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
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
  const { t } = useLang();
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
        "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-6 text-center text-sm transition-colors",
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
      <span className="text-muted-foreground">{busy ? t("processing") : label}</span>
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
  const { t } = useLang();

  if (busy === "merge" || !cv) {
    return (
      <Card variant="solid">
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          {t("rv_merging")}
        </CardContent>
      </Card>
    );
  }

  const fs = merge?.field_sources ?? {};
  const p = cv.personal ?? {};
  const skills = cv.skills ?? {};
  const allSkills = Object.values(skills).flat();

  const PERSONAL_FIELDS: { key: string; tk: string }[] = [
    { key: "name", tk: "f_name" },
    { key: "title", tk: "f_title" },
    { key: "email", tk: "f_email" },
    { key: "phone", tk: "f_phone" },
    { key: "location", tk: "f_location" },
    { key: "github", tk: "f_github" },
    { key: "linkedin", tk: "f_linkedin" },
    { key: "portfolio", tk: "f_portfolio" },
  ];

  return (
    <Card variant="solid">
      <CardHeader>
        <CardTitle>{t("rv_title")}</CardTitle>
        <CardDescription>{t("rv_desc")}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {merge && merge.conflicts.length > 0 && (
          <div className="rounded-md border border-[hsl(var(--accent-warn))]/40 bg-[hsl(var(--accent-warn))]/10 p-3 text-xs">
            <p className="mb-1 font-medium text-[hsl(var(--accent-warn))]">
              {merge.conflicts.length} {t("rv_conflicts")}
            </p>
            <ul className="space-y-0.5 text-muted-foreground">
              {merge.conflicts.slice(0, 5).map((c, i) => (
                <li key={i}>
                  <code>{c.field}</code>: «{String(c.kept)}» ({c.kept_source}) / «{String(c.other)}» ({c.other_source})
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {PERSONAL_FIELDS.map((f) => (
            <label key={f.key} className="flex flex-col gap-1 text-xs">
              <span className="flex items-center text-muted-foreground">
                {t(f.tk)}
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
            {t("rv_summary_es")}
            <SourceBadge source={fs.summary_es} />
          </span>
          <Textarea
            rows={3}
            value={cv.summary_es ?? ""}
            onChange={(e) => onPatchField("summary_es", e.target.value)}
          />
        </label>

        <div className="grid grid-cols-3 gap-3 text-center text-xs">
          <Stat n={cv.experience?.length ?? 0} label={t("rv_exp")} />
          <Stat n={allSkills.length} label={t("rv_skills")} />
          <Stat n={cv.projects?.length ?? 0} label={t("rv_proj")} />
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
            {t("rv_json")}
          </summary>
          <Textarea
            className="mt-2 font-mono text-[11px]"
            rows={12}
            defaultValue={JSON.stringify(cv, null, 2)}
            onBlur={(e) => {
              try {
                onSetCv(JSON.parse(e.target.value));
                toast.success(t("t_json_ok"));
              } catch {
                toast.error(t("t_json_err"));
              }
            }}
          />
        </details>

        <div className="flex items-center justify-between">
          <Button variant="ghost" onClick={onBack}>
            {t("back")}
          </Button>
          <Button variant="solid" onClick={onSave} disabled={busy === "complete"}>
            {busy === "complete" ? t("saving") : t("save")}
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

function AiModeOption({
  active,
  disabled,
  title,
  desc,
  onClick,
}: {
  active: boolean;
  disabled?: boolean;
  title: string;
  desc: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "rounded-lg border px-3 py-2.5 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        active
          ? "border-[hsl(var(--accent-1))]/55 bg-[hsl(var(--accent-1))]/10"
          : "border-[hsl(var(--border))] hover:border-[hsl(var(--accent-1))]/40",
      )}
    >
      <div className="text-sm font-medium">{title}</div>
      <div className="text-[11px] text-muted-foreground">{desc}</div>
    </button>
  );
}
