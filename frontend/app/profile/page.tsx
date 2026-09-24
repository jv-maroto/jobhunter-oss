"use client";

import Link from "next/link";
import { Brain, CheckCircle2, FileText, RefreshCcw, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCareerAnalysis, useCareerSources, useRefreshCareerSources, useStartCareerAnalysis, type CareerAnalysis } from "@/hooks/useCareerAnalysis";
import { apiDate, publicJobUrl } from "@/lib/utils";

const STATUS: Record<CareerAnalysis["status"], string> = {
  queued: "Análisis en cola",
  running: "Analizando tu perfil",
  completed: "Análisis guardado",
  failed: "El análisis no se completó",
  interrupted: "Análisis interrumpido",
};
const FIT = { direct: "Encaje directo", adjacent: "Perfil cercano", exploratory: "Por explorar" };

export default function ProfilePage() {
  const query = useCareerAnalysis();
  const start = useStartCareerAnalysis();
  const sources = useCareerSources();
  const refresh = useRefreshCareerSources();
  const refreshing = refresh.isPending || sources.data?.refresh?.status === "running";
  const latest = query.data?.analysis;
  const saved = latest?.status === "completed" ? latest : query.data?.last_completed;
  const result = saved?.result;
  const running = latest?.status === "queued" || latest?.status === "running";
  const busy = running || start.isPending;
  const failed = latest?.status === "failed" || latest?.status === "interrupted";
  const stale = query.data?.stale;
  const date = apiDate(saved?.finished_at);

  async function analyze() {
    try {
      const response = await start.mutateAsync();
      toast.info(response.reused
        ? "Tu perfil no ha cambiado: reutilizamos el análisis guardado."
        : "Análisis iniciado. Puedes salir de esta página y volver después.");
    } catch (error) {
      toast.error("No se pudo iniciar el análisis", { description: error instanceof Error ? error.message : "Vuelve a intentarlo." });
    }
  }

  async function refreshSources() {
    try {
      await refresh.mutateAsync();
      toast.info("Actualizando las fuentes públicas guardadas. Analiza tu perfil cuando termine para incorporar los cambios.");
    } catch (error) {
      toast.error("No se pudieron actualizar las fuentes", { description: error instanceof Error ? error.message : "Vuelve a intentarlo." });
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Brain className="h-5 w-5 text-[hsl(var(--accent-1))]" />Tu próximo trabajo empieza por tu perfil</CardTitle>
          <p className="max-w-3xl text-sm text-muted-foreground">Descubre profesiones que puedes explorar y las experiencias que respaldan cada recomendación. El análisis se guarda; cambiar países o preferencias de búsqueda no lo repite.</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button onClick={analyze} disabled={busy || refreshing || query.isLoading || !query.data}>
              {busy ? <RefreshCcw className="animate-spin" /> : <Brain />}
              {busy ? "Analizando…" : failed ? "Reintentar análisis" : stale ? "Analizar perfil actualizado" : saved ? "Comprobar y reutilizar análisis" : "Analizar mi perfil"}
            </Button>
            <Button asChild variant="outline"><Link href="/settings"><FileText />Editar datos del CV</Link></Button>
            <Button asChild variant="ghost"><Link href="/settings/search">Preferencias de búsqueda</Link></Button>
          </div>
          <p className="text-xs text-muted-foreground">Se reutilizan tu CV, los datos de proyectos y las fuentes públicas guardadas. Actualiza GitHub y el portafolio en la sección de fuentes para incorporar contenido nuevo antes de analizar.</p>
          {query.isLoading && <div role="status"><p className="mb-2 text-sm">Cargando tu análisis guardado…</p><Skeleton className="h-12 w-full" /></div>}
          {query.isError && <div role="alert" className="space-y-2 text-sm text-amber-400"><p>No se pudo actualizar el estado. {query.data ? "Se muestra la última información recibida." : "Comprueba la conexión con el servidor."}</p><Button variant="outline" size="sm" onClick={() => query.refetch()}>Reintentar conexión</Button></div>}
          {latest && <div role="status" aria-live="polite" className="flex items-start gap-2 rounded-lg border border-[hsl(var(--border))] p-3 text-sm">
            {failed ? <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" /> : running ? <RefreshCcw className="mt-0.5 h-4 w-4 shrink-0 animate-spin" /> : <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />}
            <div className="min-w-0 space-y-1"><p className="font-medium">{STATUS[latest.status]}</p>
              {running && <p className="text-muted-foreground">El estado se actualiza automáticamente. El resultado quedará guardado cuando termine.</p>}
              {failed && <p className="text-muted-foreground break-words">{latest.error || "Puedes reintentar el análisis."} {result ? "Conservamos el último análisis completado debajo." : ""}</p>}
              {date && <p className="text-xs text-muted-foreground">Último resultado completado: {date.toLocaleString("es-ES")}</p>}
            </div>
          </div>}
          {stale && <p role="status" className="rounded-lg border border-amber-400/30 p-3 text-sm text-amber-400">Tus datos guardados han cambiado. {result ? "Las recomendaciones de abajo pertenecen a la versión anterior; actualiza el análisis para usar los cambios." : "Analiza la versión actual para obtener recomendaciones."}</p>}
          {!query.isLoading && !query.isError && !latest && <p className="text-sm text-muted-foreground">Aún no tienes un análisis. Revisa tus datos y pulsa «Analizar mi perfil» para crear el primero.</p>}
        </CardContent>
      </Card>

      <Card variant="glass"><CardHeader><CardTitle>GitHub y portafolio</CardTitle><p className="text-sm text-muted-foreground">Actualiza las direcciones configuradas en tu perfil. Se guarda una lectura limitada de páginas, README y archivos de proyecto; no se ejecuta su código ni se revisa todo el repositorio.</p></CardHeader><CardContent className="space-y-3">
        <Button variant="outline" onClick={refreshSources} disabled={refreshing || busy || sources.isLoading || !sources.data}><RefreshCcw className={refreshing ? "animate-spin" : undefined} />{refreshing ? "Actualizando fuentes…" : "Actualizar GitHub y portafolio"}</Button>
        {sources.isLoading && <p role="status" className="text-sm text-muted-foreground">Cargando fuentes guardadas…</p>}
        {sources.isError && <div role="alert" className="text-sm"><p>No se pudieron consultar las fuentes.</p><Button variant="ghost" size="sm" onClick={() => sources.refetch()}>Reintentar conexión</Button></div>}
        {refreshing && <p role="status" className="text-sm text-muted-foreground">La actualización sigue en segundo plano. Al terminar, pulsa «Analizar mi perfil» para incorporar el contenido.</p>}
        {sources.data?.refresh?.status === "completed" && <p role="status" className="text-sm text-muted-foreground">Actualización terminada. Revisa el estado de cada fuente y analiza el perfil para incorporar los cambios.</p>}
        {sources.data?.refresh?.error && <p role="alert" className="text-sm text-amber-400 break-words">{sources.data.refresh.error}</p>}
        {!sources.isLoading && !sources.isError && sources.data?.sources.length === 0 && <p className="text-sm text-muted-foreground">Todavía no hay contenido público guardado. Comprueba tus enlaces en <Link href="/settings" className="underline">los datos del perfil</Link> y actualiza las fuentes.</p>}
        <ul className="space-y-2">{sources.data?.sources.map((source) => { const url = publicJobUrl(source.url); return <li key={source.id} className="rounded-lg border border-[hsl(var(--border))] p-3 text-sm"><div className="flex flex-wrap justify-between gap-2"><span className="font-medium">{source.kind}</span><span className={source.status === "ready" ? "text-emerald-400" : "text-amber-400"}>{source.status === "ready" ? "Contenido guardado" : "No se pudo actualizar"}</span></div>{url ? <a href={url} target="_blank" rel="noreferrer" className="break-all text-[hsl(var(--accent-1))] underline">{source.url}</a> : <p className="break-all">{source.url}</p>}{source.fetched_at && <p className="mt-1 text-xs text-muted-foreground">Última lectura: {apiDate(source.fetched_at)?.toLocaleString("es-ES") ?? "Fecha desconocida"}</p>}{source.truncated && <p className="text-xs text-muted-foreground">Lectura parcial: se alcanzó el límite de contenido.</p>}{source.error && <p className="mt-1 break-words text-xs text-amber-400">{source.error}</p>}</li>; })}</ul>
      </CardContent></Card>

      {result && <>
        {result.method === "baseline" && <p role="status" className="rounded-lg border border-amber-400/30 p-4 text-sm text-amber-400">Inventario sin IA: se han organizado tus datos guardados, pero aún no se ha realizado una nueva exploración de profesiones. Configura un proveedor en <Link href="/settings/ai" className="underline">Ajustes de IA</Link> y vuelve a analizar tu perfil.</p>}
        <Card variant="glass"><CardHeader><CardTitle>Tu punto de partida</CardTitle></CardHeader><CardContent><p className="whitespace-pre-line text-sm leading-relaxed">{result.summary}</p></CardContent></Card>
        {result.conflicts?.length > 0 && <Card variant="glass"><CardHeader><CardTitle>Datos que necesitan revisión</CardTitle></CardHeader><CardContent><ul className="space-y-3">{result.conflicts.map((conflict, index) => <li key={index} className="rounded-lg border border-amber-400/30 p-3 text-sm"><p className="font-medium break-words">{conflict.path}</p><p className="mt-1 text-muted-foreground">Hay valores distintos para este dato. Comprueba las versiones antes de usarlo en una candidatura.</p><pre className="mt-2 whitespace-pre-wrap break-words text-xs">{JSON.stringify(conflict.variants, null, 2)}</pre></li>)}</ul></CardContent></Card>}
        <section aria-labelledby="career-roles" className="space-y-3">
          <div><h2 id="career-roles" className="text-lg font-semibold">Profesiones para explorar</h2><p className="text-sm text-muted-foreground">Orientaciones basadas en tus datos, no garantías de contratación. Las evidencias declaradas aún requieren tu revisión.</p></div>
          {result.roles.length === 0 && <p className="text-sm text-muted-foreground">No hay recomendaciones suficientes con los datos disponibles. Amplía tu experiencia y proyectos en el perfil.</p>}
          <div className="grid gap-4 md:grid-cols-2">
            {result.roles.map((role, index) => <Card key={`${role.title}-${index}`} variant="glass">
              <CardHeader><p className="text-xs font-medium text-[hsl(var(--accent-1))]">{FIT[role.fit]}</p><CardTitle>{role.title}</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm"><p>{role.reason}</p>
                {role.evidence_ids.length > 0 && <div><h3 className="mb-1 font-medium">En qué se apoya</h3><ul className="space-y-1">{role.evidence_ids.map((id) => { const evidence = result.evidence.find((item) => item.id === id); return <li key={id}><a className="text-[hsl(var(--accent-1))] underline underline-offset-2" href={`#evidence-${id}`}>{evidence?.value || id}</a></li>; })}</ul></div>}
                {role.gaps.length > 0 && <div><h3 className="mb-1 font-medium">Por reforzar o confirmar</h3><ul className="list-disc space-y-1 pl-4 text-muted-foreground">{role.gaps.map((gap, i) => <li key={i}>{gap}</li>)}</ul></div>}
              </CardContent>
            </Card>)}
          </div>
        </section>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card variant="glass"><CardHeader><CardTitle>Evidencias del perfil</CardTitle><p className="text-xs text-muted-foreground">Información de tu perfil y de las fuentes guardadas. No implica verificación independiente.</p></CardHeader><CardContent><ul className="space-y-3">{result.evidence.map((item) => <li id={`evidence-${item.id}`} key={item.id} className="scroll-mt-24 rounded-lg border border-[hsl(var(--border))] p-3 text-sm"><p className="whitespace-pre-line break-words">{item.value}</p><p className="mt-1 break-words text-xs text-muted-foreground">{item.source === "profile" ? "Perfil guardado" : item.source} · {item.path}</p></li>)}</ul>{!result.evidence.length && <p className="text-sm text-muted-foreground">No hay evidencias detalladas en este resultado.</p>}</CardContent></Card>
          <Card variant="glass"><CardHeader><CardTitle>Incertidumbres y límites</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><p className="text-muted-foreground">Comprueba fechas, nivel de idiomas, formación y autoría de proyectos antes de usar estas recomendaciones.</p>{result.limitations.length ? <ul className="list-disc space-y-2 pl-4">{result.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>No se han detallado límites adicionales. Esto no confirma que todos los datos estén completos o libres de contradicciones.</p>}<Button asChild variant="outline" size="sm"><Link href="/settings">Corregir mi perfil</Link></Button></CardContent></Card>
        </div>
      </>}
    </div>
  );
}
