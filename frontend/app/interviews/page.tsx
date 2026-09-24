"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Brain, MessageSquare, Save } from "lucide-react";
import { api } from "@/lib/api";
import { apiDate, localDateTimeInput } from "@/lib/utils";
import { useApplications } from "@/hooks/useApplications";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

interface Interview {
  id: number; application_id: number; job_snapshot: { title?: string; company?: string }; stage: string; language: string;
  scheduled_at: string | null; notes: string; feedback: string; status: string; prep_status: string; prep_error: string | null; prep_stale: boolean;
  prep_result: { method: string; summary: string; questions: { question: string; focus: string; source_ids: string[]; answer_outline: string[] }[]; practice_tasks: string[]; limitations: string[]; evidence: { id: string; text: string; kind: string }[] } | null;
}
const INPUT = "mt-1 w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm";
const STAGES = { screening: "Primer contacto", technical: "Técnica", behavioral: "Competencias", final: "Final" };
const PREP: Record<string, string> = { idle: "Sin preparar", queued: "En cola", running: "Preparando", completed: "Preparación guardada", failed: "No se pudo preparar", interrupted: "Preparación interrumpida" };

export default function InterviewsPage() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["interviews"], queryFn: () => api<{ items: Interview[]; total: number }>("/interviews"), refetchInterval: (query) => query.state.data?.items.some((item) => ["queued", "running"].includes(item.prep_status)) ? 2000 : 15000 });
  const applications = useApplications({ limit: 100 });
  const [applicationId, setApplicationId] = useState("");
  const [stage, setStage] = useState("technical");
  const [language, setLanguage] = useState("es");
  const [schedule, setSchedule] = useState("");
  const [notes, setNotes] = useState("");
  const mutation = useMutation({ mutationFn: ({ path, body }: { path: string; body: unknown }) => api(path, { method: "POST", body: JSON.stringify(body) }), onSuccess: () => qc.invalidateQueries({ queryKey: ["interviews"] }) });

  async function create(event: React.FormEvent) {
    event.preventDefault();
    try { await mutation.mutateAsync({ path: "/interviews", body: { application_id: Number(applicationId), stage, language, scheduled_at: schedule ? new Date(schedule).toISOString() : null, notes } }); toast.success("Entrevista guardada. Ya puedes preparar las preguntas."); setNotes(""); }
    catch (error) { toast.error(error instanceof Error ? error.message : "No se pudo crear la entrevista"); }
  }

  return <div className="mx-auto max-w-6xl space-y-5">
    <Card variant="glass"><CardHeader><CardTitle className="flex items-center gap-2"><MessageSquare className="h-5 w-5" />Prepara tu próxima entrevista</CardTitle><p className="text-sm text-muted-foreground">Practica con el anuncio y los documentos guardados de una candidatura concreta. Las respuestas son esquemas para completar con tu experiencia real.</p></CardHeader><CardContent>
      <form onSubmit={create} className="space-y-4"><fieldset disabled={mutation.isPending} className="space-y-4">
        <label className="block text-sm">Candidatura<select className={INPUT} value={applicationId} onChange={(e) => setApplicationId(e.target.value)}><option value="">Selecciona una candidatura</option>{applications.data?.items.filter((item) => item.application_id).map((item) => <option key={item.application_id} value={item.application_id!}>#{item.application_id} · {item.job.title} · {item.job.company}</option>)}</select></label>
        <label className="block text-xs text-muted-foreground">O introduce el ID de una candidatura anterior que no aparezca en la lista<input type="number" required min={1} step={1} className={INPUT} value={applicationId} onChange={(e) => setApplicationId(e.target.value)} /></label>
        {applications.isError && <p role="alert" className="text-sm text-amber-400">No se pudo cargar la lista de candidaturas. Puedes introducir su ID o <button type="button" className="underline" onClick={() => applications.refetch()}>reintentar</button>.</p>}
        <div className="grid gap-4 md:grid-cols-3"><label className="text-sm">Etapa<select className={INPUT} value={stage} onChange={(e) => setStage(e.target.value)}>{Object.entries(STAGES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="text-sm">Idioma de práctica<select className={INPUT} value={language} onChange={(e) => setLanguage(e.target.value)}><option value="es">Español</option><option value="en">Inglés</option></select></label><label className="text-sm">Fecha y hora local (opcional)<input className={INPUT} type="datetime-local" value={schedule} onChange={(e) => setSchedule(e.target.value)} /></label></div>
        <label className="block text-sm">Contexto y notas<textarea rows={3} maxLength={10000} className={INPUT} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Formato, temas anunciados o aspectos que quieres practicar" /></label>
        <Button type="submit" disabled={!applicationId || mutation.isPending}><Save />{mutation.isPending ? "Guardando…" : "Crear entrevista"}</Button>
      </fieldset></form>
    </CardContent></Card>
    <section aria-labelledby="interview-list" className="space-y-4"><h2 id="interview-list" className="text-lg font-semibold">Mis entrevistas</h2>{list.isLoading && <p role="status">Cargando entrevistas…</p>}{list.isError && <div role="alert"><p>No se pudieron actualizar las entrevistas.</p><Button onClick={() => list.refetch()} variant="outline">Reintentar</Button></div>}{list.data?.items.length === 0 && <p className="text-sm text-muted-foreground">No hay entrevistas guardadas. Crea una para empezar a practicar.</p>}{list.data?.items.map((interview) => <InterviewCard key={interview.id} interview={interview} />)}</section>
  </div>;
}

function InterviewCard({ interview }: { interview: Interview }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [notes, setNotes] = useState(interview.notes ?? "");
  const [feedback, setFeedback] = useState(interview.feedback ?? "");
  const [schedule, setSchedule] = useState(localDateTimeInput(interview.scheduled_at));
  const [stage, setStage] = useState(interview.stage);
  const [language, setLanguage] = useState(interview.language);
  const [status, setStatus] = useState(interview.status);
  const mutation = useMutation({ mutationFn: ({ method, body, suffix = "" }: { method: string; body?: unknown; suffix?: string }) => api<{ reused?: boolean }>(`/interviews/${interview.id}${suffix}`, { method, ...(body ? { body: JSON.stringify(body) } : {}) }), onSuccess: () => qc.invalidateQueries({ queryKey: ["interviews"] }) });
  const busy = mutation.isPending || ["queued", "running"].includes(interview.prep_status);
  const result = interview.prep_result;
  async function save(event: React.FormEvent) { event.preventDefault(); try { await mutation.mutateAsync({ method: "PATCH", body: { notes, feedback, scheduled_at: schedule ? new Date(schedule).toISOString() : null, stage, language, status } }); setEditing(false); toast.success("Entrevista actualizada"); } catch (error) { toast.error(error instanceof Error ? error.message : "No se pudo guardar"); } }
  async function prepare() { try { const response = await mutation.mutateAsync({ method: "POST", suffix: "/prepare", body: {} }); toast.info(response.reused ? "Se reutiliza la preparación guardada." : "Preparación iniciada en segundo plano."); } catch (error) { toast.error(error instanceof Error ? error.message : "No se pudo preparar"); } }
  return <Card variant="glass"><CardHeader><CardTitle>{interview.job_snapshot?.title || `Entrevista #${interview.id}`}</CardTitle><p className="text-sm text-muted-foreground">{interview.job_snapshot?.company} · {STAGES[interview.stage as keyof typeof STAGES] ?? interview.stage} · {interview.language === "en" ? "Inglés" : "Español"} · {interview.status === "completed" ? "Completada" : interview.status === "cancelled" ? "Cancelada" : "Planificada"}</p>{interview.scheduled_at && <p className="text-sm">{apiDate(interview.scheduled_at)?.toLocaleString("es-ES")}</p>}</CardHeader><CardContent className="space-y-4">
    <div className="flex flex-wrap gap-2"><Button onClick={prepare} disabled={busy || editing || interview.status === "cancelled"}><Brain />{busy ? "Preparando…" : result ? "Comprobar y reutilizar preparación" : "Preparar preguntas"}</Button><Button variant="outline" disabled={busy} onClick={() => { setEditing(!editing); setNotes(interview.notes ?? ""); setFeedback(interview.feedback ?? ""); setSchedule(localDateTimeInput(interview.scheduled_at)); setStage(interview.stage); setLanguage(interview.language); setStatus(interview.status); }}>{editing ? "Cancelar edición" : "Editar y anotar resultado"}</Button><Button asChild variant="ghost"><Link href={`/applications/${interview.application_id}`}>Ver candidatura #{interview.application_id}</Link></Button></div>
    {interview.prep_stale && <p className="text-sm text-amber-400">Esta preparación corresponde a otro idioma o etapa. Genera la versión actual antes de practicar.</p>}<p role="status" className="text-xs text-muted-foreground">{PREP[interview.prep_status] ?? interview.prep_status}</p>{interview.prep_error && <p role="alert" className="break-words text-sm text-amber-400">{interview.prep_error}</p>}
    {editing && <form onSubmit={save} className="space-y-3 rounded-lg border border-[hsl(var(--border))] p-3"><fieldset disabled={busy} className="space-y-3"><div className="grid gap-3 md:grid-cols-2"><label className="text-sm">Etapa<select className={INPUT} value={stage} onChange={(e) => setStage(e.target.value)}>{Object.entries(STAGES).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label className="text-sm">Idioma<select className={INPUT} value={language} onChange={(e) => setLanguage(e.target.value)}><option value="es">Español</option><option value="en">Inglés</option></select></label><label className="text-sm">Fecha y hora local<input type="datetime-local" className={INPUT} value={schedule} onChange={(e) => setSchedule(e.target.value)} /></label><label className="text-sm">Estado<select className={INPUT} value={status} onChange={(e) => setStatus(e.target.value)}><option value="planned">Planificada</option><option value="completed">Completada</option><option value="cancelled">Cancelada</option></select></label></div><label className="block text-sm">Notas<textarea rows={3} maxLength={10000} className={INPUT} value={notes} onChange={(e) => setNotes(e.target.value)} /></label><label className="block text-sm">Resultado y aprendizajes<textarea rows={3} maxLength={10000} className={INPUT} value={feedback} onChange={(e) => setFeedback(e.target.value)} /></label><Button type="submit"><Save />Guardar cambios</Button></fieldset></form>}
    {!editing && interview.notes && <p className="whitespace-pre-wrap text-sm">{interview.notes}</p>}{!editing && interview.feedback && <div className="text-sm"><h3 className="font-medium">Resultado y aprendizajes</h3><p className="whitespace-pre-wrap">{interview.feedback}</p></div>}
    {result && <div className="space-y-4 border-t border-[hsl(var(--border))] pt-4">{result.method === "baseline" && <p className="text-sm text-amber-400">Guía sin IA: comprueba sus límites. Puedes configurar un proveedor de IA para generar una preparación más específica.</p>}<p className="text-sm whitespace-pre-line">{result.summary}</p><div className="grid gap-3 md:grid-cols-2">{result.questions.map((question, index) => <article key={index} className="rounded-lg border border-[hsl(var(--border))] p-3 text-sm"><h3 className="font-medium">{index + 1}. {question.question}</h3><p className="mt-1 text-xs text-muted-foreground">{question.focus}</p><ul className="mt-2 list-disc space-y-1 pl-4">{question.answer_outline.map((item, i) => <li key={i}>{item}</li>)}</ul>{question.source_ids.length > 0 && <details className="mt-3"><summary className="cursor-pointer text-xs text-[hsl(var(--accent-1))]">Evidencias para construir tu respuesta</summary>{question.source_ids.map((id) => { const evidence = result.evidence.find((item) => item.id === id); return <p key={id} className="mt-2 whitespace-pre-wrap break-words text-xs text-muted-foreground">{evidence?.text || id}</p>; })}</details>}</article>)}</div>{result.practice_tasks.length > 0 && <div className="text-sm"><h3 className="font-medium">Ejercicios de práctica</h3><ul className="mt-2 list-disc space-y-1 pl-4">{result.practice_tasks.map((task, index) => <li key={index}>{task}</li>)}</ul></div>}<details className="text-sm"><summary className="cursor-pointer">Límites de la preparación</summary><ul className="mt-2 list-disc space-y-1 pl-4 text-muted-foreground">{result.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details></div>}
  </CardContent></Card>;
}
