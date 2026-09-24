"use client";

import * as React from "react";
import Link from "next/link";
import { Filter, RefreshCcw, ListChecks, Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { JobTable } from "@/components/jobs/JobTable";
import { useJobsPage, type JobLocationFilter } from "@/hooks/useJobs";
import { AddJobDialog } from "@/components/jobs/AddJobDialog";
import { useDiscovery } from "@/hooks/useDiscovery";
import { api } from "@/lib/api";
import { JOB_COUNTRIES } from "@/lib/jobCountries";
import { JOB_STATUSES, type JobStatus, type JobTrack } from "@/lib/types";
import { TrackFilter } from "@/components/jobs/TrackFilter";

const SOURCES = ["all", "manual", "linkedin", "indeed", "remotive", "tecnoempleo", "jobspy-sysadmin"];
const STATUS_OPTIONS = JOB_STATUSES;

export default function JobsPage() {
  const [country, setCountry] = React.useState("");
  const [locationFilter, setLocationFilter] = React.useState<JobLocationFilter>("all");
  const [track, setTrack] = React.useState<JobTrack | undefined>(undefined);
  const [minScore, setMinScore] = React.useState(0);
  const [source, setSource] = React.useState<string>("all");
  const [status, setStatus] = React.useState<JobStatus>("detected");
  const [offset, setOffset] = React.useState(0);
  const [verifiedOnly, setVerifiedOnly] = React.useState(false);
  const [starting, setStarting] = React.useState(false);

  const jobs = useJobsPage({
    verified_only: verifiedOnly,
    location_filter: locationFilter,
    country,
    min_score: minScore,
    source: source === "all" ? undefined : source,
    status,
    track,
    limit: 50,
    offset,
  });

  const { refetch: refetchScrape, data: scrapeStatus, isError: scrapeStatusError } = useDiscovery();
  const scraping = starting || scrapeStatus?.running === true;
  const triggerScrape = async () => {
    setStarting(true);
    try {
      setTrack(undefined); setMinScore(0); setSource("all"); setStatus("detected"); setOffset(0);
      const res = await api<{ status: string }>("/jobs/discover-now", { method: "POST" });
      toast.info(res.status === "already_running" ? "Ya estoy buscando para ti." : "Búsqueda iniciada", { description: "Las ofertas irán apareciendo mientras busco." });
      await refetchScrape();
    } catch (error) {
      toast.error("No se pudo iniciar la búsqueda", { description: error instanceof Error ? error.message : "Vuelve a intentarlo." });
    } finally { setStarting(false); }
  };

  const list = jobs.data?.items ?? [];
  const total = jobs.data?.total ?? 0;

  return (
    <div className="space-y-4">
      <Card variant="glass">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="inline-flex items-center gap-2">
              <ListChecks className="h-4 w-4 text-[hsl(var(--accent-1))]" />
              Trabajos para ti
            </CardTitle>
            <p className="text-[11px] text-muted-foreground mt-1">
              Busca con tu perfil en las fuentes disponibles. Después decides qué ubicaciones y trabajos te interesan.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" size="sm" className="mono">
              {total} ofertas
            </Badge>
            <Button
              size="default"
              onClick={triggerScrape}
              disabled={scraping}
            >
              {scraping ? (
                <Loader2 className="animate-spin" />
              ) : (
                <RefreshCcw />
              )}
              {scraping ? "Buscando ofertas…" : "Buscar trabajos para mí"}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border p-3 text-sm" role="status" aria-live="polite">
            {scrapeStatusError ? (
              <p>No se puede consultar el estado de la búsqueda. Comprueba la conexión con el servidor.</p>
            ) : !scrapeStatus ? (
              <p>Consultando el estado de la búsqueda…</p>
            ) : scraping ? (
              <p>Buscando para ti… {scrapeStatus?.completed_sources ?? 0} de {scrapeStatus?.total_sources ?? 0} fuentes consultadas · {scrapeStatus?.inserted ?? 0} ofertas nuevas. Puedes revisarlas mientras continúo.</p>
            ) : scrapeStatus.finished_at ? (
              <>
                <p>Última búsqueda: {new Date(scrapeStatus.finished_at).toLocaleString("es-ES")}</p>
                <p>{scrapeStatus.scraped} encontradas · {scrapeStatus.inserted} nuevas guardadas · {scrapeStatus.duplicates} duplicadas.</p>
                {scrapeStatus.error && <p className="text-rose-400">La búsqueda terminó con un error: {scrapeStatus.error}</p>}
                <p className="text-xs text-muted-foreground">La búsqueda recorre los mercados y empresas con fuentes disponibles. Las ubicaciones desconocidas se conservan para revisar.</p>
              </>
            ) : (
              <p>Pulsa «Buscar trabajos para mí». No hace falta elegir países ni crear campañas.</p>
            )}
          </div>
          <p className="text-xs text-muted-foreground">{verifiedOnly ? "Mostrando ofertas con vigencia comprobada. Puedes incluir las pendientes desde los filtros." : "Ofertas ordenadas por puntuación. Las caducadas se ocultan. Indeed solo aparece con vigencia confirmada; las demás indican si está pendiente."}</p>
          <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5 text-sm">País de la oferta
            <select className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--surface))] px-3 py-2 text-foreground" value={country} onChange={(event) => { setCountry(event.target.value); setLocationFilter("all"); setOffset(0); }}>
              <option value="">Todos los países</option>
              <option value="unknown">Sin país concreto o por confirmar</option>
              {JOB_COUNTRIES.map(({code,label}) => <option key={code} value={code}>{label}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-sm">Dónde quieres trabajar
            <select className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--surface))] px-3 py-2 text-foreground" value={locationFilter} onChange={(event) => { setLocationFilter(event.target.value as JobLocationFilter); setCountry(""); setOffset(0); }}>
              <option value="all">Todo el mundo</option>
              <option value="spain_remote">España remoto</option>
              <option value="remote_worldwide">Remoto todo el mundo</option>
              <option value="spain">España solo</option>
            </select>
          </label>
          </div>
          <p className="text-xs text-muted-foreground">El país corresponde a la ubicación anunciada del puesto, no a la sede de la empresa.</p>
          {locationFilter !== "all" && <p className="text-xs text-muted-foreground">{locationFilter === "remote_worldwide" ? "Anuncios que indican remoto desde cualquier país. Revisa sus requisitos de contratación." : locationFilter === "spain_remote" ? "Puestos remotos cuya ubicación indica España." : "Puestos en España de cualquier modalidad: presencial, híbrida o remota."}</p>}
          <details className="rounded-lg border border-[hsl(var(--border))] p-3"><summary className="cursor-pointer text-sm text-muted-foreground">Filtrar resultados u otras opciones</summary><div className="mt-4 space-y-4">
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={verifiedOnly} onChange={(event) => { setVerifiedOnly(event.target.checked); setOffset(0); }} />Solo ofertas con vigencia comprobada</label>
          <TrackFilter value={track} onChange={(value) => { setTrack(value); setOffset(0); }} />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground inline-flex items-center gap-1">
                <Filter className="h-3 w-3" />
                Estado
              </label>
              <Select value={status} onValueChange={(value) => { setStatus(value as JobStatus); setOffset(0); }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((s) => (
                    <SelectItem key={s} value={s} className="capitalize">
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
                Fuente
              </label>
              <Select value={source} onValueChange={(value) => { setSource(value); setOffset(0); }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SOURCES.map((s) => (
                    <SelectItem key={s} value={s} className="capitalize">
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground inline-flex items-center justify-between w-full">
                <span>Encaje mínimo</span>
                <span className="mono text-[hsl(var(--accent-1))]">
                  {minScore}
                </span>
              </label>
              <Slider
                value={[minScore]}
                onValueChange={(v) => { setMinScore(v[0]); setOffset(0); }}
                min={0}
                max={100}
                step={5}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-sm"><AddJobDialog /><Link href="/profile" className="underline">Mi perfil</Link><Link href="/campaigns" className="underline">Campañas avanzadas</Link><Link href="/boards" className="underline">Gestionar fuentes</Link></div>
          </div></details>
          {jobs.isFetching && jobs.data && <p role="status" className="text-sm text-muted-foreground">Actualizando ofertas de trabajo…</p>}
          {jobs.error && jobs.data && <p role="alert" className="text-sm text-amber-400">No se pudieron actualizar las ofertas. Se muestran las últimas guardadas. <button className="underline" onClick={() => void jobs.refetch()}>Reintentar</button></p>}
          {jobs.isLoading ? (
            <div role="status" aria-live="polite" className="space-y-3"><p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Cargando ofertas de trabajo…</p><Skeleton className="h-64 w-full" /></div>
          ) : jobs.error && !jobs.data ? (
            <p role="alert" className="text-sm text-rose-400">No se pudieron cargar las ofertas. <button className="underline" onClick={() => void jobs.refetch()}>Reintentar</button></p>
          ) : (
            <JobTable jobs={list} />
          )}
          {total > 50 && <div className="flex justify-between items-center gap-3 text-sm">
            <span>{offset + 1}–{Math.min(offset + list.length, total)} de {total}</span>
            <div className="flex gap-2"><Button variant="outline" disabled={offset === 0 || jobs.isFetching} onClick={() => setOffset(Math.max(0, offset - 50))}>Anterior</Button><Button variant="outline" disabled={offset + 50 >= total || jobs.isFetching} onClick={() => setOffset(offset + 50)}>Siguiente</Button></div>
          </div>}
        </CardContent>
      </Card>
    </div>
  );
}
