"use client";

import * as React from "react";
import {
  Users,
  Sparkles,
  Building2,
  ExternalLink,
  RefreshCcw,
  UserPlus,
  Target,
} from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import {
  useCreateNetworkingPerson,
  useNetworkingPeople,
  useNetworkingSuggestions,
} from "@/hooks/useNetworking";
import type { NetworkingSuggestion } from "@/lib/networking";
import type { Person } from "@/lib/types";

function SkillChips({ skills }: { skills: string[] }) {
  if (!skills?.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {skills.slice(0, 5).map((s) => (
        <Badge key={s} variant="mono" size="sm">
          {s}
        </Badge>
      ))}
    </div>
  );
}

function SuggestionCard({ s }: { s: NetworkingSuggestion }) {
  return (
    <Card variant="glass" hover="lift">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-sm font-medium truncate font-[family-name:var(--font-display)]">
              {s.full_name ?? s.headline}
            </div>
            {s.full_name && (
              <div className="text-xs text-muted-foreground truncate">
                {s.headline}
              </div>
            )}
            {s.company && (
              <div className="mt-0.5 inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                <Building2 className="h-3 w-3" />
                {s.company}
              </div>
            )}
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <Badge
              variant={s.priority >= 85 ? "solid" : "secondary"}
              size="sm"
              className="mono normal-case tracking-normal"
            >
              P{s.priority}
            </Badge>
            <Badge
              variant={s.kind === "person" ? "success" : "outline"}
              size="sm"
            >
              {s.kind === "person" ? "contacto" : "arquetipo"}
            </Badge>
          </div>
        </div>

        <p className="text-[11px] leading-relaxed italic text-muted-foreground/85">
          {s.reason}
        </p>

        <SkillChips skills={s.skill_match} />
      </CardContent>
    </Card>
  );
}

function PersonRow({ person }: { person: Person }) {
  return (
    <Card variant="glass" hover="lift">
      <CardContent className="p-4 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-sm font-medium truncate font-[family-name:var(--font-display)]">
              {person.full_name}
            </div>
            <div className="text-xs text-muted-foreground truncate">
              {person.headline || "—"}
            </div>
            {person.company && (
              <div className="mt-0.5 inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                <Building2 className="h-3 w-3" />
                {person.company}
              </div>
            )}
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <Badge
              variant={person.priority >= 85 ? "solid" : "secondary"}
              size="sm"
              className="mono normal-case tracking-normal"
            >
              P{person.priority}
            </Badge>
            <Badge variant="outline" size="sm">
              {person.status}
            </Badge>
          </div>
        </div>

        {person.reason && (
          <p className="text-[11px] leading-relaxed italic text-muted-foreground/85 line-clamp-3">
            {person.reason}
          </p>
        )}

        {person.profile_url && !person.profile_url.startsWith("manual://") && (
          <div className="flex justify-end">
            <a
              href={person.profile_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-[hsl(var(--accent-1))] hover:underline"
            >
              Ver perfil
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function NetworkingPage() {
  const suggestions = useNetworkingSuggestions();
  const people = useNetworkingPeople();
  const createPerson = useCreateNetworkingPerson();

  const [fullName, setFullName] = React.useState("");
  const [headline, setHeadline] = React.useState("");
  const [company, setCompany] = React.useState("");
  const [profileUrl, setProfileUrl] = React.useState("");

  const sData = suggestions.data;
  const suggestionList = sData?.suggestions ?? [];
  const peopleList = people.data ?? [];

  const submitPerson = async () => {
    if (!fullName.trim()) {
      toast.error("El nombre es obligatorio");
      return;
    }
    try {
      await createPerson.mutateAsync({
        full_name: fullName.trim(),
        headline: headline.trim() || undefined,
        company: company.trim() || undefined,
        profile_url: profileUrl.trim() || undefined,
      });
      toast.success("Persona añadida a la cola");
      setFullName("");
      setHeadline("");
      setCompany("");
      setProfileUrl("");
    } catch (e) {
      toast.error("No se pudo crear", { description: String(e).slice(0, 120) });
    }
  };

  return (
    <div className="space-y-5">
      {/* Header stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <Card variant="glass" hover="lift" className="p-4">
          <div className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Sugerencias
          </div>
          <div className="mt-2 mono text-2xl font-semibold tabular-nums leading-none text-[hsl(var(--accent-1))]">
            {suggestionList.length}
          </div>
          <div className="mt-1 text-[10px] text-muted-foreground">
            según tus skills
          </div>
        </Card>
        <Card variant="glass" hover="lift" className="p-4">
          <div className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Para conectar
          </div>
          <div className="mt-2 mono text-2xl font-semibold tabular-nums leading-none text-foreground">
            {peopleList.length}
          </div>
          <div className="mt-1 text-[10px] text-muted-foreground">
            en cola
          </div>
        </Card>
        <Card variant="glass" hover="lift" className="p-4">
          <div className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Empresas objetivo
          </div>
          <div className="mt-2 mono text-2xl font-semibold tabular-nums leading-none text-foreground">
            {sData?.companies_used?.length ?? 0}
          </div>
          <div className="mt-1 text-[10px] text-muted-foreground">
            donde aplicaste {sData?.ai_used ? "· IA" : ""}
          </div>
        </Card>
      </div>

      {/* Sugerencias */}
      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <div>
              <CardTitle className="inline-flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-[hsl(var(--accent-1))]" />
                Sugerencias
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                A quién conectar según tus skills y las empresas a las que has
                aplicado.
              </p>
            </div>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => suggestions.refetch()}
              disabled={suggestions.isFetching}
            >
              <RefreshCcw
                className={suggestions.isFetching ? "animate-spin" : ""}
              />
              Recalcular
            </Button>
          </div>
          {!!sData?.skills_used?.length && (
            <div className="mt-2">
              <SkillChips skills={sData.skills_used} />
            </div>
          )}
        </CardHeader>
        <CardContent>
          {suggestions.isLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : suggestionList.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[hsl(var(--border))] p-6 text-center text-xs text-muted-foreground">
              <Target className="mx-auto mb-2 h-5 w-5 opacity-60" />
              No hay sugerencias todavía. Aplica a ofertas y completa tus skills
              en el CV para generar objetivos de networking.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {suggestionList.map((s, i) => (
                <SuggestionCard key={`${s.headline}-${i}`} s={s} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Para conectar */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="inline-flex items-center gap-2">
            <Users className="h-4 w-4 text-[hsl(var(--accent-2))]" />
            Para conectar
          </CardTitle>
          <p className="text-[11px] text-muted-foreground">
            Tu cola de personas. Añade contactos manualmente o trabaja los
            sugeridos.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Add manual person */}
          <div className="grid grid-cols-1 gap-2 rounded-lg border border-[hsl(var(--border))] bg-white/[0.02] p-3 md:grid-cols-2">
            <Input
              placeholder="Nombre completo *"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="text-xs"
            />
            <Input
              placeholder="Headline / rol (ej. Backend Lead)"
              value={headline}
              onChange={(e) => setHeadline(e.target.value)}
              className="text-xs"
            />
            <Input
              placeholder="Empresa (opcional)"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              className="text-xs"
            />
            <Input
              placeholder="URL del perfil (opcional)"
              value={profileUrl}
              onChange={(e) => setProfileUrl(e.target.value)}
              className="text-xs"
            />
            <div className="md:col-span-2">
              <Button
                size="sm"
                shimmer
                onClick={submitPerson}
                disabled={createPerson.isPending}
                className="w-full"
              >
                <UserPlus className="h-3.5 w-3.5" />
                Añadir a la cola
              </Button>
            </div>
          </div>

          {people.isLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : peopleList.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[hsl(var(--border))] p-6 text-center text-xs text-muted-foreground">
              Cola vacía. Añade contactos arriba o desde las sugerencias.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {peopleList.map((p) => (
                <PersonRow key={p.id} person={p} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
