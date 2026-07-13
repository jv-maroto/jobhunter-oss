"use client";

import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { COUNTRY_OPTIONS, REGION_PRESETS } from "@/lib/onboarding";
import { TOS_COLORS, type PlatformInfo } from "@/lib/searchProfile";
import { useRunScrape, useSearchProfile, useUpdateSearchProfile } from "@/hooks/useSearchProfile";
import { useAiSettings, useUpdateAiSettings } from "@/hooks/useAiSettings";

export default function SearchSettingsPage() {
  const { data, isLoading } = useSearchProfile();
  const update = useUpdateSearchProfile();
  const runScrape = useRunScrape();

  const [preset, setPreset] = React.useState<string | null>(null);
  const [regions, setRegions] = React.useState<string[]>([]);
  const [platforms, setPlatforms] = React.useState<Record<string, boolean>>({});
  const [queriesAuto, setQueriesAuto] = React.useState(true);
  const [manualQueries, setManualQueries] = React.useState("");
  const [seeded, setSeeded] = React.useState(false);

  // Sembrar el estado local una vez con lo que viene del backend.
  React.useEffect(() => {
    if (!data || seeded) return;
    const sp = data.search_preferences ?? {};
    setPreset((sp.region_preset as string) ?? null);
    setRegions((sp.regions as string[]) ?? []);
    setPlatforms((sp.platforms as Record<string, boolean>) ?? {});
    setQueriesAuto(sp.queries_auto !== false);
    setManualQueries(((sp.queries as string[]) ?? []).join("\n"));
    setSeeded(true);
  }, [data, seeded]);

  if (isLoading || !data) {
    return <div className="text-sm text-muted-foreground">Cargando perfil de búsqueda…</div>;
  }

  const isChecked = (p: PlatformInfo) => platforms[p.id] ?? p.enabled_by_default;
  const togglePlatform = (id: string, def: boolean) =>
    setPlatforms((m) => ({ ...m, [id]: !(m[id] ?? def) }));

  // Preset y países concretos se COMBINAN (p.ej. Remoto + España/Alemania como preferencia).
  const pickPreset = (id: string) => setPreset((cur) => (cur === id ? null : id));
  const toggleCountry = (iso: string) =>
    setRegions((r) => (r.includes(iso) ? r.filter((x) => x !== iso) : [...r, iso]));

  async function save() {
    const presetRegions = preset
      ? REGION_PRESETS.find((p) => p.id === preset)?.regions ?? []
      : [];
    const effectiveRegions: string[] = Array.from(new Set([...presetRegions, ...regions]));
    if (effectiveRegions.length === 0) {
      toast.error("Elige al menos una región o país");
      return;
    }
    try {
      await update.mutateAsync({
        region_preset: preset ?? "custom",
        regions: effectiveRegions,
        platforms,
        queries_auto: queriesAuto,
        queries: queriesAuto
          ? []
          : manualQueries
              .split("\n")
              .map((q) => q.trim())
              .filter(Boolean),
      });
      setSeeded(false); // re-sembrar con la respuesta (incluye nuevas plataformas sugeridas)
      toast.success("Preferencias guardadas");
    } catch {
      toast.error("No se pudo guardar");
    }
  }

  async function scrapeNow() {
    try {
      const res = await runScrape.mutateAsync();
      toast.success(`Buscadas ${res.scraped} · ${res.inserted} nuevas · ${res.duplicates} dup`);
    } catch {
      toast.error("El scraping falló (revisa el backend / jobspy)");
    }
  }

  const discovery = data.suggested_platforms.filter((p) => p.method !== "apply_only");
  const applyOnly = data.suggested_platforms.filter((p) => p.method === "apply_only");

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold">Dónde buscar</h1>
        <p className="text-sm text-muted-foreground">
          Elige países y plataformas. Activamos los scrapers relevantes y derivamos las búsquedas de
          tu perfil.
        </p>
      </div>

      <Card variant="solid">
        <CardHeader>
          <CardTitle>Regiones</CardTitle>
          <CardDescription>Un preset o países concretos.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            {REGION_PRESETS.map((p) => (
              <Chip key={p.id} active={preset === p.id} onClick={() => pickPreset(p.id)}>
                {p.label}
              </Chip>
            ))}
          </div>
          <div>
            <p className="mb-2 text-xs text-muted-foreground">O países concretos:</p>
            <div className="flex flex-wrap gap-2">
              {COUNTRY_OPTIONS.map((c) => (
                <Chip key={c.iso} active={regions.includes(c.iso)} onClick={() => toggleCountry(c.iso)}>
                  {c.label}
                </Chip>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card variant="solid">
        <CardHeader>
          <CardTitle>Plataformas</CardTitle>
          <CardDescription>
            Sugeridas según tus regiones. Guarda para refrescar la lista.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {discovery.length === 0 && (
            <p className="text-xs text-muted-foreground">
              Guarda tus regiones para ver las plataformas disponibles.
            </p>
          )}
          {discovery.map((p) => (
            <PlatformRow key={p.id} p={p} checked={isChecked(p)} onToggle={() => togglePlatform(p.id, p.enabled_by_default)} />
          ))}

          {applyOnly.length > 0 && (
            <div className="mt-3 border-t border-[hsl(var(--border))] pt-3">
              <p className="mb-2 text-xs text-muted-foreground">
                Solo para autorrellenar al aplicar (no aportan ofertas al pipeline):
              </p>
              {applyOnly.map((p) => (
                <PlatformRow key={p.id} p={p} checked={isChecked(p)} onToggle={() => togglePlatform(p.id, p.enabled_by_default)} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card variant="solid">
        <CardHeader>
          <CardTitle>Búsquedas</CardTitle>
          <CardDescription>Derivadas de tu perfil, o manuales.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-1.5">
            {data.queries_preview.map((q, i) => (
              <span key={i} className="rounded bg-white/5 px-2 py-0.5 text-[11px] text-muted-foreground">
                {q}
              </span>
            ))}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={queriesAuto}
              onChange={(e) => setQueriesAuto(e.target.checked)}
            />
            Derivar búsquedas automáticamente de mi perfil
          </label>
          {!queriesAuto && (
            <Textarea
              rows={4}
              placeholder="Una búsqueda por línea"
              value={manualQueries}
              onChange={(e) => setManualQueries(e.target.value)}
            />
          )}
          <AiBoostToggle />
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Button variant="outline" onClick={scrapeNow} disabled={runScrape.isPending}>
          {runScrape.isPending ? "Buscando…" : "Buscar ahora"}
        </Button>
        <Button variant="solid" onClick={save} disabled={update.isPending}>
          {update.isPending ? "Guardando…" : "Guardar preferencias"}
        </Button>
      </div>
    </div>
  );
}

function AiBoostToggle() {
  const { data } = useAiSettings();
  const update = useUpdateAiSettings();
  const enabled = data?.ai_scraping_enabled ?? false;

  async function toggle() {
    try {
      const res = await update.mutateAsync({ ai_scraping_enabled: !enabled });
      toast.success(
        res.ai_scraping_enabled ? "IA en la búsqueda activada" : "IA en la búsqueda desactivada",
      );
    } catch {
      toast.error("No se pudo cambiar (configura la IA en Ajustes › IA)");
    }
  }

  return (
    <div className="mt-1 flex items-start justify-between gap-3 rounded-md border border-[hsl(var(--border))] px-3 py-2.5">
      <div className="min-w-0">
        <p className="text-sm font-medium">Potenciar búsqueda con IA (queries + re-rank)</p>
        <p className="text-xs text-muted-foreground">
          Genera variantes de búsqueda desde tu perfil y reordena las ofertas nuevas por relevancia.
          Requiere IA disponible (Ajustes › IA).
        </p>
      </div>
      <button
        onClick={toggle}
        disabled={!data || update.isPending}
        className={cn(
          "mt-0.5 h-6 w-11 shrink-0 rounded-full border transition-colors disabled:opacity-50",
          enabled
            ? "border-[hsl(var(--accent-1))]/55 bg-[hsl(var(--accent-1))]/30"
            : "border-[hsl(var(--border))] bg-white/5",
        )}
        aria-pressed={enabled}
      >
        <span
          className={cn(
            "block h-4 w-4 rounded-full bg-foreground transition-transform",
            enabled ? "translate-x-6" : "translate-x-1",
          )}
        />
      </button>
    </div>
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

function PlatformRow({
  p,
  checked,
  onToggle,
}: {
  p: PlatformInfo;
  checked: boolean;
  onToggle: () => void;
}) {
  // Una plataforma "planned" esta en el catalogo pero NO tiene scraper detras.
  // Antes se pintaba un toggle normal: el usuario la activaba, no se buscaba
  // nada y nadie se lo decia. Ahora se deshabilita y se explica por que.
  const planned = p.status === "planned" || !p.implemented;
  const disabled = planned && p.method !== "apply_only";

  return (
    <div
      className={cn(
        "flex items-center justify-between rounded-md border border-[hsl(var(--border))] px-3 py-2",
        disabled && "opacity-55",
      )}
    >
      <div className="flex min-w-0 flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <span className="text-sm">{p.label}</span>
          <span className="rounded border border-[hsl(var(--border))] px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground">
            {p.method}
          </span>
          {p.tos_risk && (
            <span className={cn("rounded border px-1.5 py-0.5 text-[10px] uppercase", TOS_COLORS[p.tos_risk])}>
              ToS {p.tos_risk}
            </span>
          )}
          {disabled && (
            <span className="rounded border border-[hsl(38_95%_55%)]/40 bg-[hsl(38_95%_55%)]/10 px-1.5 py-0.5 text-[10px] uppercase text-[hsl(38_95%_60%)]">
              sin scraper
            </span>
          )}
        </div>
        {disabled && (
          <span className="text-[11px] text-muted-foreground">
            Declarada en el catálogo pero aún no implementada: no se buscarán
            ofertas aquí.
          </span>
        )}
        {!disabled && p.requires_env && (
          <span className="text-[11px] text-muted-foreground">
            Necesita <code className="mono">{p.requires_env.toUpperCase()}</code> en
            el .env; sin la clave se desactiva sola.
          </span>
        )}
      </div>
      <button
        onClick={disabled ? undefined : onToggle}
        disabled={disabled}
        title={
          disabled ? "Todavía no hay scraper para esta plataforma" : undefined
        }
        className={cn(
          "h-6 w-11 shrink-0 rounded-full border transition-colors",
          disabled && "cursor-not-allowed",
          checked && !disabled
            ? "border-[hsl(var(--accent-1))]/55 bg-[hsl(var(--accent-1))]/30"
            : "border-[hsl(var(--border))] bg-white/5",
        )}
        aria-pressed={checked && !disabled}
      >
        <span
          className={cn(
            "block h-4 w-4 rounded-full bg-foreground transition-transform",
            checked && !disabled ? "translate-x-6" : "translate-x-1",
          )}
        />
      </button>
    </div>
  );
}
