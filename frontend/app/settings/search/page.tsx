"use client";

import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useLang } from "@/lib/i18n";
import { EMPLOYMENT_LABELS, JOB_TRACK_LABELS } from "@/lib/types";
import { COUNTRY_OPTIONS, REGION_PRESETS } from "@/lib/onboarding";
import { TOS_COLORS, type PlatformInfo } from "@/lib/searchProfile";
import { useRunScrape, useSearchProfile, useUpdateSearchProfile } from "@/hooks/useSearchProfile";
import { useAiSettings, useUpdateAiSettings } from "@/hooks/useAiSettings";

export default function SearchSettingsPage() {
  const { data, isLoading, error, refetch } = useSearchProfile();
  const { lang, t } = useLang();
  const tr = (es: string, en: string) => lang === "es" ? es : en;
  const update = useUpdateSearchProfile();
  const runScrape = useRunScrape();

  const [preset, setPreset] = React.useState<string | null>(null);
  const [regions, setRegions] = React.useState<string[]>([]);
  const [platforms, setPlatforms] = React.useState<Record<string, boolean>>({});
  const [queriesAuto, setQueriesAuto] = React.useState(true);
  const [manualQueries, setManualQueries] = React.useState("");
  const [roles, setRoles] = React.useState<string[]>([]);
  const [customRole, setCustomRole] = React.useState("");
  const [employmentTypes, setEmploymentTypes] = React.useState<string[]>([]);
  const [seniority, setSeniority] = React.useState("");
  const [remoteOnly, setRemoteOnly] = React.useState(false);
  const [relocate, setRelocate] = React.useState(false);
  const [residence, setResidence] = React.useState("");
  const [salaryMin, setSalaryMin] = React.useState("");
  const [salaryMax, setSalaryMax] = React.useState("");
  const [currency, setCurrency] = React.useState("");
  const [seeded, setSeeded] = React.useState(false);

  // Sembrar el estado local una vez con lo que viene del backend.
  React.useEffect(() => {
    if (!data || seeded) return;
    const sp = data.search_preferences ?? {};
    setPreset((sp.region_preset as string) ?? null);
    setRegions((sp.regions as string[]) ?? data.regions ?? []);
    setPlatforms((sp.platforms as Record<string, boolean>) ?? {});
    setQueriesAuto(sp.queries_auto !== false);
    setManualQueries(((sp.queries as string[]) ?? []).join("\n"));
    setRoles(Array.isArray(sp.roles) ? sp.roles as string[] : []);
    setEmploymentTypes(Array.isArray(sp.employment_types) ? sp.employment_types as string[] : []);
    setSeniority(String(sp.seniority ?? ""));
    setRemoteOnly(sp.remote_only === true);
    setRelocate(sp.willing_to_relocate === true);
    setResidence(String(sp.residence_country ?? ""));
    setSalaryMin(String(("salary_min" in sp ? sp.salary_min : sp.salary_min_eur) ?? ""));
    setSalaryMax(String(("salary_max" in sp ? sp.salary_max : sp.salary_max_eur) ?? ""));
    setCurrency(String(("salary_currency" in sp ? sp.salary_currency : (sp.salary_min_eur != null || sp.salary_max_eur != null ? "EUR" : "")) ?? ""));
    setSeeded(true);
  }, [data, seeded]);

  if (error) {
    return <div role="alert" className="space-y-3 text-sm">
      <p>{tr("No se pudo cargar el perfil de búsqueda.", "Could not load the search profile.")}</p>
      <Button onClick={() => void refetch()}>{tr("Reintentar", "Retry")}</Button>
    </div>;
  }
  if (isLoading || !data) {
    return <div className="text-sm text-muted-foreground">Cargando perfil de búsqueda…</div>;
  }

  const isChecked = (p: PlatformInfo) => platforms[p.id] ?? p.enabled_by_default;
  const togglePlatform = (id: string, def: boolean) =>
    setPlatforms((m) => ({ ...m, [id]: !(m[id] ?? def) }));

  const pickPreset = (id: string) => {
    setPreset(id);
    setRegions([...(REGION_PRESETS.find((p) => p.id === id)?.regions ?? [])]);
  };
  const toggleCountry = (iso: string) => {
    setPreset(null);
    setRegions((r) => r.includes(iso) ? r.filter((x) => x !== iso) : [...r, iso]);
  };
  const toggleRole = (role: string) => setRoles((current) => current.includes(role) ? current.filter((r) => r !== role) : [...current, role]);
  function addRole() {
    const value = customRole.trim();
    if (value && !roles.some((r) => r.toLowerCase() === value.toLowerCase())) setRoles((current) => [...current, value]);
    setCustomRole("");
  }

  async function save() {
    const presetRegions = preset
      ? REGION_PRESETS.find((p) => p.id === preset)?.regions ?? []
      : [];
    const effectiveRegions: string[] = Array.from(new Set([...presetRegions, ...regions]));
    if (effectiveRegions.length === 0) {
      toast.error("Elige al menos una región o país");
      return false;
    }
    const min = salaryMin.trim() ? Number(salaryMin) : null;
    const max = salaryMax.trim() ? Number(salaryMax) : null;
    if ((min != null && (!Number.isFinite(min) || min < 0)) || (max != null && (!Number.isFinite(max) || max < 0)) || (min != null && max != null && min > max)) {
      toast.error(tr("Revisa el rango salarial: mínimo ≤ máximo, sin números negativos.", "Check the salary range: minimum ≤ maximum, with no negative numbers."));
      return false;
    }
    if ((min != null || max != null) && !currency) {
      toast.error(tr("Elige la moneda del rango salarial.", "Choose the currency for your salary range."));
      return false;
    }
    if (!roles.length) {
      toast.error(tr("Elige al menos un rol.", "Choose at least one role."));
      return false;
    }
    if (!queriesAuto && !manualQueries.trim()) {
      toast.error(tr("Añade una búsqueda o activa las búsquedas automáticas.", "Add a search query or enable automatic searches."));
      return false;
    }
    try {
      await update.mutateAsync({
        roles,
        employment_types: employmentTypes,
        seniority: seniority || null,
        remote_only: remoteOnly,
        willing_to_relocate: relocate,
        residence_country: residence || null,
        salary_min: min,
        salary_max: max,
        salary_currency: currency || null,
        region_preset: preset ?? "custom",
        regions: effectiveRegions,
        platforms,
        queries_auto: queriesAuto,
        queries: manualQueries.split("\n").map((q) => q.trim()).filter(Boolean),
      });
      setSeeded(false); // re-sembrar con la respuesta (incluye nuevas plataformas sugeridas)
      toast.success("Preferencias guardadas");
      return true;
    } catch {
      toast.error("No se pudo guardar");
      return false;
    }
  }

  async function scrapeNow() {
    if (!(await save())) return;
    try {
      const res = await runScrape.mutateAsync();
      const exclusions = [
        res.filtered_geography ? `${res.filtered_geography} ${tr("fuera de la región", "outside your regions")}` : "",
        res.unconfirmed_geography ? `${res.unconfirmed_geography} ${tr("con ubicación sin confirmar", "with unconfirmed location")}` : "",
        res.filtered_remote ? `${res.filtered_remote} ${tr("sin modalidad remota compatible", "without compatible remote work")}` : "",
        res.filtered_employment ? `${res.filtered_employment} ${tr("con contrato incompatible", "with incompatible contract type")}` : "",
        res.filtered_seniority ? `${res.filtered_seniority} ${tr("con nivel incompatible", "with incompatible seniority")}` : "",
      ].filter(Boolean);
      toast.success(`Buscadas ${res.scraped} · ${res.inserted} nuevas · ${res.duplicates} dup`, {
        description: exclusions.length ? exclusions.join(" · ") : undefined,
      });
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
          <CardTitle>{tr("Regiones y modalidad", "Regions and work arrangement")}</CardTitle>
          <CardDescription>{tr("Un preset reemplaza los países seleccionados. Puedes después ajustarlos uno a uno.", "A preset replaces the selected countries. You can then adjust them individually.")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            {REGION_PRESETS.map((p) => (
              <Chip key={p.id} active={preset === p.id} onClick={() => pickPreset(p.id)}>
                {t(({only_spain: "rg_preset_es", only_switzerland: "rg_preset_ch", all_europe: "rg_preset_eu", remote_worldwide: "rg_preset_remote"})[p.id])}
              </Chip>
            ))}
          </div>
          <div>
            <p className="mb-2 text-xs text-muted-foreground">O países concretos:</p>
            <div className="flex flex-wrap gap-2">
              {COUNTRY_OPTIONS.map((c) => (
                <Chip key={c.iso} active={regions.includes(c.iso)} onClick={() => toggleCountry(c.iso)}>
                  {t(`c_${c.iso}`)}
                </Chip>
              ))}
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} />
            {tr("Solo puestos remotos", "Remote roles only")}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={relocate} onChange={(e) => setRelocate(e.target.checked)} />
            {tr("Estoy dispuesto a trasladarme", "I am willing to relocate")}
          </label>
          <label className="flex flex-col gap-1 text-xs">
            {tr("País de residencia (para elegibilidad remota)", "Country of residence (for remote eligibility)")}
            <select className="rounded-md border bg-[hsl(var(--surface))] p-2" value={residence} onChange={(e) => setResidence(e.target.value)}>
              <option value="">{tr("Sin especificar", "Not specified")}</option>
              {residence && !COUNTRY_OPTIONS.some((c) => c.iso === residence) && <option value={residence}>{residence}</option>}
              {COUNTRY_OPTIONS.filter((c) => c.iso !== "REMOTE").map((c) => <option key={c.iso} value={c.iso}>{t(`c_${c.iso}`)}</option>)}
            </select>
          </label>
          <p className="text-xs text-muted-foreground">{tr("Suiza y remoto son preferencias de búsqueda. La ubicación permitida para trabajar en remoto y la autorización laboral se deben comprobar en cada oferta.", "Switzerland and remote work are search preferences. Check each listing for remote work eligibility and work authorization.")}</p>
        </CardContent>
      </Card>

      <Card variant="solid">
        <CardHeader>
          <CardTitle>{tr("Roles objetivo", "Target roles")}</CardTitle>
          <CardDescription>{tr("Estos roles guían las búsquedas y la afinidad; no añaden experiencia ni habilidades a tu CV.", "These roles guide searches and matching; they do not add experience or skills to your CV.")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {Array.from(new Set([...Object.values(JOB_TRACK_LABELS), ...roles])).map((role) => <Chip key={role} active={roles.includes(role)} onClick={() => toggleRole(role)}>{role}</Chip>)}
          </div>
          <div className="flex gap-2">
            <Input aria-label={t("roles_add_ph")} placeholder={t("roles_add_ph")} value={customRole} onChange={(e) => setCustomRole(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addRole(); } }} />
            <Button onClick={addRole} disabled={!customRole.trim()}>{t("roles_add_btn")}</Button>
          </div>
        </CardContent>
      </Card>

      <Card variant="solid">
        <CardHeader>
          <CardTitle>{tr("Contrato y nivel", "Contract and seniority")}</CardTitle>
          <CardDescription>{tr("Sin selección se permiten todos. Jornada completa no confirma contrato indefinido; los datos sin confirmar siguen visibles.", "An empty selection allows all. Full-time does not confirm a permanent contract; unconfirmed details remain visible.")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {Object.entries(EMPLOYMENT_LABELS).map(([id, label]) => <Chip key={id} active={employmentTypes.includes(id)} onClick={() => setEmploymentTypes((current) => current.includes(id) ? current.filter((type) => type !== id) : [...current, id])}>{label}</Chip>)}
          </div>
          <label className="flex flex-col gap-1 text-xs">{tr("Nivel objetivo", "Target seniority")}
            <select className="rounded-md border bg-[hsl(var(--surface))] p-2" value={seniority} onChange={(e) => setSeniority(e.target.value)}>
              <option value="">{tr("Cualquier nivel", "Any seniority")}</option>
              {Array.from(new Set(["junior", "mid", "senior", "lead", ...(seniority ? [seniority] : [])])).map((level) => <option key={level} value={level}>{level}</option>)}
            </select>
          </label>
        </CardContent>
      </Card>

      <Card variant="solid">
        <CardHeader>
          <CardTitle>{tr("Objetivo salarial anual bruto", "Gross annual salary target")}</CardTitle>
          <CardDescription>{tr("Opcional. Indica la moneda; no convertimos importes entre monedas.", "Optional. Choose the currency; amounts are not converted between currencies.")}</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs">{tr("Mínimo", "Minimum")}<Input type="number" min="0" value={salaryMin} onChange={(e) => setSalaryMin(e.target.value)} /></label>
          <label className="flex flex-col gap-1 text-xs">{tr("Máximo", "Maximum")}<Input type="number" min="0" value={salaryMax} onChange={(e) => setSalaryMax(e.target.value)} /></label>
          <label className="flex flex-col gap-1 text-xs">{tr("Moneda", "Currency")}
            <select className="rounded-md border bg-[hsl(var(--surface))] p-2" value={currency} onChange={(e) => setCurrency(e.target.value)}>
              <option value="">{tr("Elegir moneda", "Choose currency")}</option>
              {Array.from(new Set(["CHF", "EUR", "USD", "GBP", ...(currency ? [currency] : [])])).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
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
              aria-label={tr("Búsquedas manuales, una por línea", "Manual searches, one per line")}
              placeholder="Una búsqueda por línea"
              value={manualQueries}
              onChange={(e) => setManualQueries(e.target.value)}
            />
          )}
          <AiBoostToggle />
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button variant="outline" onClick={scrapeNow} disabled={runScrape.isPending || update.isPending}>
          {runScrape.isPending ? "Buscando…" : tr("Guardar y buscar", "Save and search")}
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
        aria-label="Potenciar búsqueda con IA"
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
      type="button"
      aria-pressed={active}
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
        <div className="flex flex-wrap items-center gap-2">
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
        aria-label={p.label}
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
