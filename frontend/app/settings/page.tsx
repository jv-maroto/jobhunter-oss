"use client";

import * as React from "react";
import Link from "next/link";
import { useTheme } from "next-themes";
import { Save, Bot, Palette, FileJson, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import { onboardingApi } from "@/lib/onboarding";
import { JOB_TRACK_LABELS, type JobTrack } from "@/lib/types";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [cv, setCv] = React.useState("");
  const [loadError, setLoadError] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [loaded, setLoaded] = React.useState(false);
  const [applicationDocuments, setApplicationDocuments] = React.useState<unknown>(null);

  const loadCv = React.useCallback(() => api<Record<string, unknown>>("/settings/cv_master").then((remote) => {
    setCv(JSON.stringify(remote, null, 2));
    setApplicationDocuments(remote.application_documents);
    setLoaded(true);
  }).catch(() => setLoadError(true)), []);
  React.useEffect(() => { void loadCv(); }, [loadCv]);

  const saveCv = async () => {
    if (!loaded || saving) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(cv);
    } catch (e) {
      toast.error("CV JSON inválido", { description: String(e) });
      return;
    }
    setSaving(true);
    try {
      await api("/settings/cv_master", {
        method: "PUT",
        body: JSON.stringify(parsed),
      });
      setApplicationDocuments((parsed as Record<string, unknown>).application_documents);
      toast.success("cv_master.json guardado");
    } catch {
      toast.error("No se pudo guardar. Se conserva tu edición para reintentarlo.");
    } finally { setSaving(false); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="inline-flex items-center gap-2">
            <Bot className="h-4 w-4 text-[hsl(var(--accent-1))]" />
            IA y claves
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Elige proveedor (Anthropic / OpenAI / Gemini), IA local con Ollama (gratis) o
            sin IA, y gestiona tus API keys desde la pantalla de IA.
          </p>
          <Link href="/settings/ai">
            <Button variant="outline">Ir a Ajustes de IA →</Button>
          </Link>
        </CardContent>
      </Card>

      <Card variant="glass">
        <CardHeader>
          <CardTitle className="inline-flex items-center gap-2">
            <Palette className="h-4 w-4 text-[hsl(var(--accent-2))]" />
            Appearance
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">Dark mode</div>
              <div className="text-[11px] text-muted-foreground">
                Tema oscuro estilo Command Center por defecto.
              </div>
            </div>
            <Switch
              aria-label="Dark mode"
              checked={theme === "dark"}
              onCheckedChange={(v) => setTheme(v ? "dark" : "light")}
            />
          </div>
          <div className="rounded-md border border-[hsl(var(--border))] bg-white/[0.02] p-3">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">
              Accent palette
            </div>
            <div className="flex items-center gap-2">
              <span className="h-6 w-6 rounded-md bg-[hsl(var(--accent-1))]" />
              <span className="h-6 w-6 rounded-md bg-[hsl(var(--accent-2))]" />
              <span className="h-6 w-6 rounded-md bg-[hsl(var(--accent-warn))]" />
              <span className="h-6 w-6 rounded-md bg-gradient-to-br from-[hsl(var(--accent-1))] to-[hsl(var(--accent-2))]" />
            </div>
          </div>
        </CardContent>
      </Card>

      <ApplicationCvCard configuration={applicationDocuments} />

      <Card variant="glass" className="lg:col-span-2">
        <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
          <div>
            <CardTitle className="inline-flex items-center gap-2">
              <FileJson className="h-4 w-4 text-[hsl(var(--accent-1))]" />
              cv_master.json
            </CardTitle>
            <p className="text-[11px] text-muted-foreground mt-1">
              Fuente de verdad para generar CVs personalizados.
              {loaded ? "" : " · Cargando…"}
            </p>
          </div>
          <Button onClick={saveCv} disabled={!loaded || saving} shimmer>
            <Save />
            Save
          </Button>
        </CardHeader>
        <CardContent>
          {loadError && <p role="alert" className="mb-3 text-sm text-rose-400">No se pudo cargar el perfil. <button className="underline" onClick={() => { setLoadError(false); void loadCv(); }}>Reintentar</button></p>}
          <Textarea
            aria-label="Perfil completo en JSON"
            disabled={!loaded || saving}
            value={cv}
            onChange={(e) => setCv(e.target.value)}
            rows={24}
            className="font-mono text-xs"
            spellCheck={false}
          />
        </CardContent>
      </Card>

      <CvStorageCard />

      <RedoOnboardingCard />
    </div>
  );
}


// ---------------------------------------------------------------------------
// CV storage — pick folder + naming scheme
// ---------------------------------------------------------------------------

type NamingOption = { key: string; label: string; example: string };
type CvStorage = {
  root_dir: string;
  naming_scheme: string;
  default_root_dir: string;
  options: NamingOption[];
};

function CvStorageCard() {
  const [config, setConfig] = React.useState<CvStorage | null>(null);
  const [rootDir, setRootDir] = React.useState("");
  const [naming, setNaming] = React.useState("");
  const [renameExisting, setRenameExisting] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const cfg = await api<CvStorage>("/settings/cv-storage");
      setConfig(cfg);
      setRootDir(cfg.root_dir);
      setNaming(cfg.naming_scheme);
    } catch (e) {
      toast.error("No se pudo cargar la configuración", {
        description: String(e).slice(0, 140),
      });
    } finally {
      setLoading(false);
    }
  }, []);
  React.useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const res = await api<{
        root_dir: string;
        naming_scheme: string;
        renamed: number;
        warnings: string[];
      }>("/settings/cv-storage", {
        method: "PUT",
        body: JSON.stringify({
          root_dir: rootDir,
          naming_scheme: naming,
          rename_existing: renameExisting,
        }),
      });
      const parts = [`Carpeta: ${res.root_dir}`, `Formato: ${res.naming_scheme}`];
      if (renameExisting) parts.push(`Renombradas: ${res.renamed}`);
      toast.success("Guardado", {
        description: parts.join(" · "),
      });
      if (res.warnings && res.warnings.length) {
        toast.warning(`${res.warnings.length} avisos`, {
          description: res.warnings.slice(0, 3).join("\n"),
        });
      }
      await load();
    } catch (e) {
      toast.error("No se pudo guardar", { description: String(e).slice(0, 140) });
    } finally {
      setSaving(false);
    }
  };

  const dirty =
    config && (rootDir !== config.root_dir || naming !== config.naming_scheme);

  return (
    <Card variant="glass" className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="inline-flex items-center gap-2">
          <FileJson className="h-4 w-4 text-[hsl(var(--accent-1))]" />
          Almacenamiento de CVs y cartas
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Elige dónde se guardan los PDFs generados y qué formato tienen los
          nombres de carpeta. Al cambiar el formato, puedes renombrar las
          carpetas existentes automáticamente.
        </p>

        {loading || !config ? (
          <p className="text-xs text-muted-foreground">Cargando…</p>
        ) : (
          <>
            <label className="block space-y-1">
              <span className="text-xs uppercase tracking-wider text-muted-foreground">
                Carpeta raíz
              </span>
              <input
                type="text"
                value={rootDir}
                onChange={(e) => setRootDir(e.target.value)}
                className="w-full rounded-md border border-[hsl(var(--border))] bg-background/40 px-3 py-2 font-mono text-xs"
                placeholder={config.default_root_dir}
                spellCheck={false}
              />
              <span className="block text-[11px] text-muted-foreground">
                Ruta absoluta. Vacío = por defecto (
                <code>{config.default_root_dir}</code>).
              </span>
            </label>

            <fieldset className="space-y-2">
              <legend className="text-xs uppercase tracking-wider text-muted-foreground">
                Formato del nombre de carpeta
              </legend>
              {config.options.map((opt) => (
                <label
                  key={opt.key}
                  className={`flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 transition-colors ${
                    naming === opt.key
                      ? "border-[hsl(var(--accent-1))]/60 bg-[hsl(var(--accent-1))]/5"
                      : "border-[hsl(var(--border))] hover:bg-background/40"
                  }`}
                >
                  <input
                    type="radio"
                    name="naming"
                    value={opt.key}
                    checked={naming === opt.key}
                    onChange={() => setNaming(opt.key)}
                    className="accent-[hsl(var(--accent-1))]"
                  />
                  <span className="flex-1 text-sm font-medium">{opt.label}</span>
                  <code className="text-[11px] text-muted-foreground">
                    {opt.example}
                  </code>
                </label>
              ))}
            </fieldset>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={renameExisting}
                onChange={(e) => setRenameExisting(e.target.checked)}
                className="accent-[hsl(var(--accent-1))]"
              />
              <span>
                Renombrar carpetas existentes al guardar
                <span className="ml-2 text-[11px] text-muted-foreground">
                  (mueve las carpetas actuales al nuevo formato/ruta y actualiza
                  las referencias)
                </span>
              </span>
            </label>

            <div className="flex justify-end gap-2 pt-1">
              <Button
                variant="outline"
                disabled={!dirty || saving}
                onClick={() => {
                  if (!config) return;
                  setRootDir(config.root_dir);
                  setNaming(config.naming_scheme);
                }}
              >
                <RotateCcw className="h-3.5 w-3.5" /> Descartar
              </Button>
              <Button onClick={save} disabled={!dirty || saving} shimmer>
                <Save className="h-3.5 w-3.5" />
                {saving ? "Guardando…" : "Guardar"}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ApplicationCvCard({ configuration }: { configuration: unknown }) {
  if (!configuration || typeof configuration !== "object") return null;
  const config = configuration as Record<string, unknown>;
  if (config.mode !== "existing") return null;
  const mappings = config.cv_by_track && typeof config.cv_by_track === "object"
    ? Object.entries(config.cv_by_track).flatMap(([track, value]) => {
        if (!value || typeof value !== "object" || !("filename" in value) || typeof value.filename !== "string") return [];
        const filename = value.filename.split(/[\\/]/).pop();
        return filename ? [{ track, filename }] : [];
      }) : [];

  return (
    <Card variant="glass" className="lg:col-span-2">
      <CardHeader>
        <CardTitle>Application CVs</CardTitle>
        <p className="text-sm text-muted-foreground">Existing PDFs, kept unchanged.</p>
      </CardHeader>
      <CardContent>
        <dl className="space-y-2 text-sm">
          {mappings.map(({ track, filename }) => (
            <div key={track} className="grid gap-1 sm:grid-cols-2 sm:gap-4">
              <dt>{JOB_TRACK_LABELS[track as JobTrack] ?? track.replaceAll("_", " ")}</dt>
              <dd className="break-words text-muted-foreground">{filename}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

/**
 * Rehacer el onboarding. El endpoint /onboarding/reset existia y estaba incluso
 * cableado en lib/onboarding.ts, pero NINGUN boton lo llamaba: una vez
 * completado el wizard no habia forma de volver a lanzarlo desde la interfaz.
 */
function RedoOnboardingCard() {
  const [busy, setBusy] = React.useState(false);
  const [confirming, setConfirming] = React.useState(false);

  const redo = async () => {
    setBusy(true);
    try {
      const res = await onboardingApi.reset();
      toast.success("Onboarding reiniciado", {
        description: "Se hizo copia de tu cv_master en app/data/cv_master_backups/.",
      });
      // El OnboardingGate ve onboarded:false y redirige al wizard.
      window.location.href = "/onboarding";
      return res;
    } catch (e) {
      toast.error("No se pudo reiniciar el onboarding", {
        description: String(e).slice(0, 120),
      });
      setBusy(false);
    }
  };

  return (
    <Card variant="glass">
      <CardHeader>
        <CardTitle className="inline-flex items-center gap-2">
          <RotateCcw className="h-4 w-4 text-[hsl(var(--accent-1))]" />
          Rehacer onboarding
        </CardTitle>
        <p className="text-[11px] text-muted-foreground mt-1">
          Vuelve a lanzar el asistente para reconstruir tu perfil desde el CV,
          GitHub o LinkedIn. Tu <code className="mono">cv_master.json</code> actual
          se conserva y se utiliza como punto de partida del nuevo borrador.
        </p>
      </CardHeader>
      <CardContent>
        {confirming ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={redo} disabled={busy} variant="destructive">
              {busy ? "Reiniciando…" : "Sí, reiniciar y abrir el asistente"}
            </Button>
            <Button
              onClick={() => setConfirming(false)}
              disabled={busy}
              variant="ghost"
            >
              Cancelar
            </Button>
          </div>
        ) : (
          <Button onClick={() => setConfirming(true)} variant="outline">
            <RotateCcw className="mr-2 h-3.5 w-3.5" />
            Rehacer onboarding
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
