"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, RefreshCcw, Save } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { apiDate, publicJobUrl } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

interface Board { id: number; name: string; provider: string; slug: string; status: string; last_refresh: { status: string; started_at: string; finished_at?: string; error?: string; staged?: number; count?: number; truncated?: boolean; note?: string } | null }
interface BoardJob { source_id: string; title: string; company: string; location: string; remote: boolean | null; description: string; url: string; description_truncated?: boolean; compensation_raw?: unknown; salary_min?: number | null; salary_max?: number | null; currency?: string }
const INPUT = "mt-1 w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm";
const PROVIDERS: Record<string, string> = { greenhouse: "Greenhouse", lever: "Lever", lever_eu: "Lever Europa", ashby: "Ashby" };

export default function BoardsPage() {
  const qc = useQueryClient();
  const boards = useQuery({ queryKey: ["boards"], queryFn: () => api<Board[]>("/search/boards?include_archived=true"), refetchInterval: (query) => query.state.data?.some((board) => board.last_refresh?.status === "running") ? 2000 : 15000 });
  const [name, setName] = useState("");
  const [provider, setProvider] = useState("greenhouse");
  const [slug, setSlug] = useState("");
  const mutation = useMutation({ mutationFn: () => api("/search/boards", { method: "POST", body: JSON.stringify({ name, provider, slug }) }), onSuccess: () => qc.invalidateQueries({ queryKey: ["boards"] }) });
  return <div className="mx-auto max-w-6xl space-y-5">
    <Card variant="glass"><CardHeader><CardTitle className="flex items-center gap-2"><Building2 className="h-5 w-5" />Ofertas directas de empresas</CardTitle><p className="text-sm text-muted-foreground">Añade los portales públicos de empresas que te interesan. Revisa sus ofertas y guarda las que quieras incorporar a tu búsqueda.</p></CardHeader><CardContent className="space-y-4"><p className="text-sm text-muted-foreground">Cada portal corresponde a una empresa concreta. Estos conectores no son un buscador de todas las empresas del mundo. Las ofertas se conservan aquí para revisión aunque su ubicación sea desconocida.</p>
      <form className="space-y-3" onSubmit={async (event) => { event.preventDefault(); try { await mutation.mutateAsync(); setName(""); setSlug(""); toast.success("Portal guardado. Actualízalo para consultar sus ofertas."); } catch (error) { toast.error(error instanceof Error ? error.message : "No se pudo guardar el portal"); } }}><fieldset disabled={mutation.isPending} className="grid gap-3 md:grid-cols-3"><label className="text-sm">Empresa<input required maxLength={160} className={INPUT} value={name} onChange={(e) => setName(e.target.value)} /></label><label className="text-sm">Plataforma<select className={INPUT} value={provider} onChange={(e) => setProvider(e.target.value)}>{Object.entries(PROVIDERS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="text-sm">Identificador del portal<input required pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,99}" maxLength={100} className={INPUT} value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="nombreempresa" /></label></fieldset><p className="text-xs text-muted-foreground">Introduce solo el identificador, sin URL. Por ejemplo, en jobs.lever.co/nombreempresa es «nombreempresa». Para Greenhouse y Ashby utiliza el identificador del portal de la empresa.</p><Button type="submit" disabled={mutation.isPending}><Save />{mutation.isPending ? "Guardando…" : "Añadir empresa"}</Button></form>
    </CardContent></Card>
    <section aria-labelledby="board-list" className="space-y-4"><h2 id="board-list" className="text-lg font-semibold">Portales guardados</h2>{boards.isLoading && <p role="status">Cargando portales…</p>}{boards.isError && <div role="alert"><p>No se pudieron actualizar los portales.</p><Button variant="outline" onClick={() => boards.refetch()}>Reintentar</Button></div>}{boards.data?.length === 0 && <p className="text-sm text-muted-foreground">Añade la primera empresa para consultar sus ofertas directamente.</p>}{boards.data?.map((board) => <BoardCard key={board.id} board={board} />)}</section>
  </div>;
}

function BoardCard({ board }: { board: Board }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(board.name);
  const running = board.last_refresh?.status === "running";
  const jobs = useQuery({ queryKey: ["board-jobs", board.id, board.last_refresh?.finished_at], queryFn: () => api<{ jobs: BoardJob[] }>(`/search/boards/${board.id}/jobs`), enabled: open, refetchInterval: running ? 2000 : false });
  const mutation = useMutation({ mutationFn: ({ method, suffix = "", body }: { method: string; suffix?: string; body?: unknown }) => api(`/search/boards/${board.id}${suffix}`, { method, ...(body ? { body: JSON.stringify(body) } : {}) }), onSuccess: () => qc.invalidateQueries({ queryKey: ["boards"] }) });
  async function act(method: string, suffix = "", body?: unknown) { try { await mutation.mutateAsync({ method, suffix, body }); return true; } catch (error) { toast.error(error instanceof Error ? error.message : "No se pudo completar la acción"); return false; } }
  const busy = mutation.isPending || running;
  const filteredJobs = jobs.data?.jobs.filter((job) => `${job.title} ${job.location}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())) ?? [];
  return <Card variant="glass"><CardHeader><CardTitle>{board.name}</CardTitle><p className="text-xs text-muted-foreground">{PROVIDERS[board.provider] ?? board.provider} · {board.slug} · {board.status === "archived" ? "Archivado" : "Activo"}</p></CardHeader><CardContent className="space-y-3">
    <div className="flex flex-wrap gap-2"><Button disabled={busy || board.status === "archived"} onClick={() => act("POST", "/refresh", {})}><RefreshCcw className={running ? "animate-spin" : undefined} />{running ? "Actualizando…" : "Actualizar ofertas"}</Button><Button variant="outline" onClick={() => setOpen(!open)}>{open ? "Ocultar ofertas" : "Revisar ofertas guardadas"}</Button><Button variant="ghost" disabled={busy} onClick={() => { setEditing(!editing); setName(board.name); }}>{editing ? "Cancelar" : "Cambiar nombre"}</Button><Button variant="ghost" disabled={busy} onClick={() => board.status === "archived" ? act("PATCH", "", { status: "active" }) : act("DELETE")}>{board.status === "archived" ? "Recuperar" : "Archivar"}</Button></div>
    {editing && <form className="flex items-end gap-2" onSubmit={async (event) => { event.preventDefault(); if (await act("PATCH", "", { name })) setEditing(false); }}><label className="flex-1 text-sm">Nombre<input className={INPUT} required maxLength={160} value={name} onChange={(e) => setName(e.target.value)} /></label><Button type="submit" disabled={busy}>Guardar</Button></form>}
    {board.last_refresh && <div role="status" className="space-y-1 text-xs text-muted-foreground"><p>Última lectura: {({ running: "en curso", finished: "terminada", failed: "falló", interrupted: "interrumpida" } as Record<string, string>)[board.last_refresh.status] ?? board.last_refresh.status} · {apiDate(board.last_refresh.finished_at ?? board.last_refresh.started_at)?.toLocaleString("es-ES")}</p>{board.last_refresh.error && <p className="break-words text-amber-400">{board.last_refresh.error}</p>}{board.last_refresh.truncated && <p>Lectura limitada: puede haber más ofertas en el portal original.</p>}</div>}
    {open && <div className="space-y-3 border-t border-[hsl(var(--border))] pt-3"><label className="block text-sm">Filtrar por puesto o ubicación<input className={INPUT} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Python, remoto, Madrid…" /></label>{jobs.data && <p role="status" className="text-xs text-muted-foreground">{filteredJobs.length} de {jobs.data.jobs.length} ofertas guardadas</p>}{jobs.isLoading && <p role="status">Cargando ofertas…</p>}{jobs.isError && <div role="alert"><p>No se pudieron cargar las ofertas guardadas.</p><Button variant="outline" onClick={() => jobs.refetch()}>Reintentar</Button></div>}{jobs.data?.jobs.length === 0 && <p className="text-sm text-muted-foreground">No hay ofertas guardadas. Actualiza el portal y comprueba su estado.</p>}{filteredJobs.map((job) => <StagedJob key={job.source_id} job={job} />)}</div>}
  </CardContent></Card>;
}

function StagedJob({ job }: { job: BoardJob }) {
  const qc = useQueryClient();
  const [remote, setRemote] = useState(job.remote === null ? "unknown" : job.remote ? "yes" : "no");
  const [importedId, setImportedId] = useState<number | null>(null);
  const url = publicJobUrl(job.url);
  const mutation = useMutation({ mutationFn: () => api<{ job: { id: number }; created: boolean }>("/jobs/import", { method: "POST", body: JSON.stringify({ title: job.title, company: job.company, description: job.description, url: job.url, location: job.location ?? "", remote: remote === "yes" }) }), onSuccess: (result) => { setImportedId(result.job.id); qc.invalidateQueries({ queryKey: ["jobs"] }); toast.success(result.created ? "Oferta guardada en tu búsqueda" : "La oferta ya existía y se ha guardado"); } });
  return <article className="space-y-2 rounded-lg border border-[hsl(var(--border))] p-3 text-sm"><h3 className="font-medium">{job.title}</h3><p className="text-muted-foreground">{job.location || "Ubicación desconocida"} · {job.remote === null ? "Modalidad sin confirmar" : job.remote ? "Remoto según la fuente" : "La fuente no lo marca remoto"}</p>{job.compensation_raw != null && <details className="text-xs"><summary>Compensación publicada por la empresa</summary><pre className="whitespace-pre-wrap break-words">{typeof job.compensation_raw === "string" ? job.compensation_raw : JSON.stringify(job.compensation_raw, null, 2)}</pre></details>}<details><summary className="cursor-pointer">Leer descripción</summary><p className="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap break-words text-xs leading-relaxed">{job.description || "Sin descripción disponible"}</p>{job.description_truncated && <p className="text-xs text-amber-400">Descripción parcial: consulta el anuncio original.</p>}</details>
    <div className="flex flex-wrap items-end gap-2"><label className="text-xs">Modalidad para guardar<select className={INPUT} value={remote} onChange={(e) => setRemote(e.target.value)} disabled={mutation.isPending || importedId !== null}><option value="unknown">Pendiente de confirmar</option><option value="yes">Remoto</option><option value="no">No remoto</option></select></label>{importedId ? <Button asChild variant="outline"><Link href={`/jobs/${importedId}`}>Ver oferta guardada</Link></Button> : <Button disabled={remote === "unknown" || mutation.isPending} onClick={async () => { try { await mutation.mutateAsync(); } catch (error) { toast.error(error instanceof Error ? error.message : "No se pudo guardar"); } }}>{mutation.isPending ? "Guardando…" : "Guardar en mi búsqueda"}</Button>}{url && <Button variant="ghost" asChild><a href={url} target="_blank" rel="noopener noreferrer">Abrir anuncio original</a></Button>}</div>{remote === "unknown" && <p className="text-xs text-muted-foreground">Revisa el anuncio y confirma la modalidad antes de importarlo. Mientras tanto se conserva en este portal.</p>}
  </article>;
}
