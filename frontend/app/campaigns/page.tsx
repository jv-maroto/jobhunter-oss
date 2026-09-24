"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe, Play, Plus, Save } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { apiDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useCareerAnalysis } from "@/hooks/useCareerAnalysis";

interface CampaignInput {
  name: string; roles: string[]; countries: string[]; modality: "remote" | "hybrid" | "onsite" | "any";
  languages: string[]; residence_country: string | null; max_queries: number; results_per_query: number; status: "draft" | "paused" | "archived";
}
interface Campaign extends CampaignInput {
  id: number;
  last_run: { status: string; started_at: string; finished_at?: string; scraped?: number; inserted?: number; duplicates?: number; job_ids?: number[]; error?: string; note?: string } | null;
}
interface Coverage { execution_enabled: boolean; countries: { code: string; configured_connectors: string[]; status: string }[] }
const EMPTY: CampaignInput = { name: "", roles: [], countries: [], modality: "any", languages: [], residence_country: null, max_queries: 8, results_per_query: 20, status: "draft" };
const INPUT = "mt-1 w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm";
const MODALITY = { any: "Cualquier modalidad", remote: "Remoto", hybrid: "Híbrido", onsite: "Presencial" };
const split = (value: string) => [...new Set(value.split(/[,\n]/).map((item) => item.trim()).filter(Boolean))];
const displayNames = new Intl.DisplayNames(["es"], { type: "region" });

export default function CampaignsPage() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<number | null>(null);
  const [form, setForm] = useState<CampaignInput>(EMPTY);
  const [rolesText, setRolesText] = useState("");
  const [languagesText, setLanguagesText] = useState("");
  const [countrySearch, setCountrySearch] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const profile = useCareerAnalysis();
  const campaigns = useQuery({ queryKey: ["campaigns", showArchived], queryFn: () => api<Campaign[]>(`/search/campaigns?include_archived=${showArchived}`), refetchInterval: (query) => query.state.data?.some((row) => row.last_run?.status === "running") ? 2000 : 15000 });
  const coverage = useQuery({ queryKey: ["campaign-coverage"], queryFn: () => api<Coverage>("/search/coverage") });
  const mutation = useMutation({ mutationFn: ({ path, method, body }: { path: string; method: string; body?: unknown }) => api(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) }), onSuccess: () => qc.invalidateQueries({ queryKey: ["campaigns"] }) });
  const selectedRoles = split(rolesText);
  const supported = new Set(coverage.data?.countries.filter((country) => country.configured_connectors.length > 0).map((country) => country.code));
  const visibleCountries = (coverage.data?.countries ?? []).filter((country) => `${displayNames.of(country.code)} ${country.code}`.toLocaleLowerCase().includes(countrySearch.toLocaleLowerCase()));
  const recommendations = profile.data?.last_completed?.result?.roles ?? [];
  const editingRunning = campaigns.data?.some((row) => row.id === editing && row.last_run?.status === "running");

  async function act(path: string, method: string, body?: unknown) {
    try { await mutation.mutateAsync({ path, method, body }); return true; }
    catch (error) { toast.error("No se pudo completar la acción", { description: error instanceof Error ? error.message : "Vuelve a intentarlo." }); return false; }
  }
  function edit(row?: Campaign) {
    setEditing(row?.id ?? null); setForm(row ? { name: row.name, roles: row.roles, countries: row.countries, modality: row.modality, languages: row.languages, residence_country: row.residence_country, max_queries: row.max_queries, results_per_query: row.results_per_query, status: row.status } : EMPTY);
    setRolesText(row?.roles.join("\n") ?? ""); setLanguagesText(row?.languages.join(", ") ?? "");
    document.getElementById("campaign-editor")?.scrollIntoView({ behavior: "smooth" });
  }
  function blockReason(row: Campaign) {
    if (!coverage.data) return "Esperando información de cobertura.";
    if (!coverage.data.execution_enabled) return "La ejecución está desactivada.";
    if (row.status === "archived") return "Recupera la campaña antes de buscar.";
    if (row.last_run?.status === "running") return "La búsqueda está en curso.";
    if (!row.roles.length || !row.countries.length) return "Añade al menos una profesión y un país.";
    if (row.countries.some((code) => !supported.has(code))) return "Hay países sin conector configurado. Puedes guardarlos, pero todavía no buscar en ellos.";
    if (row.modality === "hybrid" || row.modality === "onsite") return "El conector solo ejecuta campañas remotas o de cualquier modalidad; todavía no garantiza búsquedas exclusivamente híbridas o presenciales.";
    if (row.roles.length * row.countries.length > row.max_queries) return "Las combinaciones de profesión y país superan el presupuesto de consultas.";
    return null;
  }

  return <div className="mx-auto max-w-6xl space-y-5">
    <Card variant="glass"><CardHeader><CardTitle className="flex items-center gap-2"><Globe className="h-5 w-5" />Explora trabajos en todo el mundo</CardTitle><p className="text-sm text-muted-foreground">Guarda campañas independientes por profesión, país y modalidad. Cada búsqueda se inicia manualmente y respeta su propio límite de consultas.</p></CardHeader><CardContent className="space-y-2 text-sm"><p>Ahora se ejecutan los países con conector configurado mediante Indeed. Guardar otros países no implica que ya tengamos ofertas de ellos.</p><p className="text-muted-foreground">Los idiomas y el país de residencia son preferencias guardadas: revisa requisitos, permisos de trabajo y restricciones de cada oferta. Un empleo remoto puede estar limitado a un país.</p><Button variant="outline" asChild><Link href="/profile">Consultar recomendaciones de mi perfil</Link></Button></CardContent></Card>
    <Card variant="glass" id="campaign-editor"><CardHeader><CardTitle>{editing ? "Editar campaña" : "Nueva campaña"}</CardTitle></CardHeader><CardContent>
      <form className="space-y-4" onSubmit={async (event) => { event.preventDefault(); if (await act(editing ? `/search/campaigns/${editing}` : "/search/campaigns", editing ? "PATCH" : "POST", { ...form, roles: selectedRoles, languages: split(languagesText) })) { toast.success("Campaña guardada"); edit(); } }}>
        <fieldset disabled={mutation.isPending || editingRunning} className="space-y-4 disabled:opacity-60">
          <label className="block text-sm">Nombre de la campaña<input required maxLength={160} className={INPUT} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Python remoto en Europa" /></label>
          <div className="grid gap-4 md:grid-cols-2"><label className="block text-sm">Profesiones (una por línea)<textarea required className={INPUT} rows={4} value={rolesText} onChange={(e) => setRolesText(e.target.value)} placeholder={"Python Developer\nBackend Engineer"} /></label><div className="space-y-3"><label className="block text-sm">Modalidad<select className={INPUT} value={form.modality} onChange={(e) => setForm({ ...form, modality: e.target.value as CampaignInput["modality"] })}>{Object.entries(MODALITY).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="block text-sm">Idiomas deseados (separados por comas)<input className={INPUT} value={languagesText} onChange={(e) => setLanguagesText(e.target.value)} placeholder="Español, inglés" /></label></div></div>
          {recommendations.length > 0 && <details className="text-sm"><summary className="cursor-pointer">Añadir profesiones del análisis guardado</summary><div className="mt-2 flex flex-wrap gap-2">{recommendations.map((role, index) => <Button key={index} type="button" size="sm" variant="outline" disabled={selectedRoles.includes(role.title)} onClick={() => setRolesText([...selectedRoles, role.title].join("\n"))}><Plus />{role.title}</Button>)}</div></details>}
          <div><label htmlFor="country-filter" className="block text-sm">Países objetivo · {form.countries.length} seleccionados</label><input id="country-filter" className={INPUT} placeholder="Buscar país por nombre o código" value={countrySearch} onChange={(e) => setCountrySearch(e.target.value)} />{coverage.isError && <p role="alert" className="text-sm text-amber-400">No se pudo cargar la cobertura. <button type="button" className="underline" onClick={() => coverage.refetch()}>Reintentar</button></p>}<div className="mt-2 grid max-h-64 gap-1 overflow-y-auto rounded-lg border border-[hsl(var(--border))] p-2 sm:grid-cols-2 lg:grid-cols-3">{visibleCountries.map((country) => <label key={country.code} className="flex items-start gap-2 rounded p-2 text-sm hover:bg-white/5"><input type="checkbox" className="mt-1" checked={form.countries.includes(country.code)} onChange={(e) => setForm({ ...form, countries: e.target.checked ? [...form.countries, country.code] : form.countries.filter((code) => code !== country.code) })} /><span>{displayNames.of(country.code)} <span className="text-xs text-muted-foreground">({country.code})</span><span className="block text-xs text-muted-foreground">{supported.has(country.code) ? "Conector configurado · disponibilidad por comprobar" : "Sin conector configurado"}</span></span></label>)}</div><p className="mt-1 text-xs text-muted-foreground">Seleccionados: {form.countries.map((code) => displayNames.of(code)).join(", ") || "Ninguno"}</p></div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><label className="text-sm">País de residencia<select className={INPUT} value={form.residence_country ?? ""} onChange={(e) => setForm({ ...form, residence_country: e.target.value || null })}><option value="">Sin indicar</option>{coverage.data?.countries.map((country) => <option key={country.code} value={country.code}>{displayNames.of(country.code)}</option>)}</select></label><label className="text-sm">Máximo de consultas<input className={INPUT} type="number" required min={1} max={50} value={form.max_queries} onChange={(e) => setForm({ ...form, max_queries: Number(e.target.value) })} /></label><label className="text-sm">Resultados por consulta<input className={INPUT} type="number" required min={1} max={100} value={form.results_per_query} onChange={(e) => setForm({ ...form, results_per_query: Number(e.target.value) })} /></label><label className="text-sm">Estado<select className={INPUT} value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as CampaignInput["status"] })}><option value="draft">Borrador</option><option value="paused">Pausada</option><option value="archived">Archivada</option></select></label></div>
          <p className="text-xs text-muted-foreground">Esta selección requiere {selectedRoles.length * form.countries.length} consultas de profesión × país. El presupuesto no garantiza ese número de ofertas. Las campañas no tienen ejecución programada. Las modalidades híbrida y presencial se pueden guardar, pero todavía no ejecutar.</p>
          <div className="flex flex-wrap gap-2"><Button type="submit"><Save />{mutation.isPending ? "Guardando…" : "Guardar campaña"}</Button>{editing && <Button type="button" variant="ghost" onClick={() => edit()}>Cancelar edición</Button>}</div>
        </fieldset>
      </form>
    </CardContent></Card>
    <section aria-labelledby="saved-campaigns" className="space-y-3"><div className="flex flex-wrap items-center justify-between gap-3"><h2 id="saved-campaigns" className="text-lg font-semibold">Mis campañas</h2><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />Incluir archivadas</label></div>
      {campaigns.isLoading && <p role="status">Cargando campañas…</p>}{campaigns.isError && <div role="alert"><p>No se pudieron actualizar las campañas.</p><Button variant="outline" onClick={() => campaigns.refetch()}>Reintentar</Button></div>}
      {campaigns.data?.length === 0 && <p className="text-sm text-muted-foreground">Aún no hay campañas en esta vista. Guarda la primera arriba.</p>}
      <div className="grid gap-4 lg:grid-cols-2">{campaigns.data?.map((row) => { const blocked = blockReason(row); return <Card key={row.id} variant="glass"><CardHeader><CardTitle>{row.name}</CardTitle><p className="text-xs text-muted-foreground">{MODALITY[row.modality]} · {row.status === "archived" ? "Archivada" : row.status === "paused" ? "Pausada" : "Borrador"}</p></CardHeader><CardContent className="space-y-3 text-sm"><p>{row.roles.join(" · ") || "Sin profesiones"}</p><p className="text-muted-foreground">{row.countries.map((code) => displayNames.of(code)).join(", ") || "Sin países"}</p><p className="text-xs text-muted-foreground">Hasta {row.max_queries} consultas · {row.results_per_query} resultados por consulta</p><div className="flex flex-wrap gap-2"><Button disabled={Boolean(blocked) || mutation.isPending} onClick={() => act(`/search/campaigns/${row.id}/run`, "POST")}><Play />{row.last_run?.status === "running" ? "Buscando…" : "Buscar ofertas"}</Button><Button variant="outline" disabled={row.last_run?.status === "running"} onClick={() => edit(row)}>Editar</Button>{row.status !== "archived" && <Button variant="ghost" disabled={mutation.isPending || row.last_run?.status === "running"} onClick={() => act(`/search/campaigns/${row.id}`, "DELETE")}>Archivar</Button>}</div>{blocked && <p className="text-xs text-amber-400">{blocked}</p>}{row.last_run && <div role="status" className="space-y-1 rounded-lg border border-[hsl(var(--border))] p-3"><p>Última búsqueda: {({ running: "en curso", finished: "terminada", failed: "falló", interrupted: "interrumpida" } as Record<string, string>)[row.last_run.status] ?? row.last_run.status}</p><p className="text-xs text-muted-foreground">{apiDate(row.last_run.started_at)?.toLocaleString("es-ES")}</p>{row.last_run.status === "finished" && <p>{row.last_run.scraped ?? 0} encontradas · {row.last_run.inserted ?? 0} nuevas · {row.last_run.duplicates ?? 0} duplicadas</p>}{row.last_run.status === "finished" && <p className="text-xs text-muted-foreground">La disponibilidad del conector no está verificada: cero resultados también puede indicar un fallo de la fuente. Las ofertas ya existentes pueden conservar puntuaciones de otras búsquedas.</p>}{row.last_run.error && <p className="break-words text-amber-400">{row.last_run.error}</p>}{Boolean(row.last_run.job_ids?.length) && <details><summary className="cursor-pointer text-[hsl(var(--accent-1))]">Ver ofertas de esta búsqueda ({row.last_run.job_ids?.length})</summary><div className="mt-2 flex max-h-40 flex-wrap gap-2 overflow-y-auto">{row.last_run.job_ids?.map((id) => <Link className="underline" href={`/jobs/${id}`} key={id}>Oferta #{id}</Link>)}</div></details>}</div>}</CardContent></Card>; })}</div>
    </section>
  </div>;
}
