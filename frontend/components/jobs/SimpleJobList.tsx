"use client";

import Link from "next/link";
import { MapPin, ArrowUpRight } from "lucide-react";
import { formatSalary } from "@/lib/utils";
import type { Job } from "@/lib/types";

export function SimpleJobList({ jobs }: { jobs: Job[] }) {
  if (!jobs.length) return <p className="rounded-xl border border-dashed p-7 text-center text-sm text-muted-foreground">Todavía no hay ofertas para mostrar. Busca trabajos para tu perfil o revisa los filtros opcionales.</p>;
  return <ul className="grid gap-3 md:grid-cols-2">{jobs.map((job) => <li key={job.id} className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--surface))]/40 p-4">
    <Link href={`/jobs/${job.id}`} className="group flex h-full flex-col gap-3">
      <div><h2 className="font-semibold group-hover:text-[hsl(var(--accent-1))]">{job.title}</h2><p className="mt-1 text-sm text-muted-foreground">{job.company}</p></div>
      <p className="flex items-start gap-2 text-sm"><MapPin className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--accent-1))]" /><span>{job.location?.trim() || "Ubicación por confirmar"}{job.remote ? " · Remoto según el anuncio" : ""}</span></p>
      <p className="text-xs text-muted-foreground">{job.availability?.status === "active" ? "Vigencia comprobada" : "Vigencia sin confirmar"}{job.availability?.checked_at ? ` · ${new Date(job.availability.checked_at).toLocaleDateString("es-ES")}` : ""}</p>
      {(job.salary_min != null || job.salary_max != null) && <p className="text-sm">{formatSalary(job.salary_min, job.salary_max, job.currency, job.salary_period)}</p>}
      <p className="text-xs text-muted-foreground">{job.remote ? "Comprueba desde qué países permite trabajar." : "Consulta la modalidad y las condiciones del puesto."} Idioma y autorización de trabajo pendientes de revisar.</p>
      <div className="mt-auto flex items-center justify-between gap-2 border-t border-[hsl(var(--border))] pt-3 text-xs"><span className="text-muted-foreground">{job.source}</span><span className="inline-flex items-center gap-1 text-[hsl(var(--accent-1))]">Ver oferta y encaje<ArrowUpRight size={14} /></span></div>
    </Link>
  </li>)}</ul>;
}
