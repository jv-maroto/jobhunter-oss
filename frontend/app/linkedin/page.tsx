"use client";

/**
 * /linkedin — sólo noticias trending para LinkedIn.
 *
 * Ni comment suggestions ni personas ni devlog personal — sólo el pipeline de
 * trending news scrapeado de HN / dev.to con post generado por Claude y banner
 * AMD-style. Personal setup — quiere leerlas y publicarlas, no rellenar más UI.
 */

import * as React from "react";
import { Flame, RefreshCcw, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PostCard } from "@/components/posts/PostCard";
import { usePosts } from "@/hooks/usePosts";
import { api } from "@/lib/api";

type StartResp = { status: string; requested?: number };
type TrendingStatus = {
  running: boolean;
  stories_found: number;
  created: number;
  images_done: number;
  requested: number;
  error: string | null;
};

export default function NoticiasPage() {
  const posts = usePosts();
  const [postLang, setPostLang] = React.useState<"es" | "en">("es");

  const trending = React.useMemo(
    () =>
      (posts.data ?? [])
        .filter((p) => p.kind === "trending")
        .sort((a, b) => (b.id ?? 0) - (a.id ?? 0)),
    [posts.data],
  );

  const drafts = trending.filter((p) => p.status === "draft");
  const scheduled = trending.filter((p) => p.status === "scheduled");
  const published = trending.filter((p) => p.status === "published");

  const generateTrending = async (opts: { count?: number; replace?: boolean } = {}) => {
    const count = opts.count ?? 10;
    const replace = opts.replace ?? false;
    const label = replace
      ? `Regenerando trending (borrando drafts antiguos y trayendo ${count} nuevos)…`
      : `Trayendo top ${count} noticias tech de las últimas 24h…`;
    const toastId = toast.loading(label);
    try {
      const res = await api<StartResp>("/posts/generate-trending", {
        method: "POST",
        body: JSON.stringify({
          count,
          language: postLang,
          replace_drafts: replace,
        }),
      });
      if (res.status === "already_running") {
        toast.info("Ya hay un trending en curso — espera al final.", {
          id: toastId,
        });
      } else {
        toast.loading("Claude está comentando las noticias…", {
          id: toastId,
          description: "Tarda 30-90s. Puedes seguir trabajando.",
        });
      }
      const pollId = window.setInterval(async () => {
        try {
          const s = await api<TrendingStatus>("/posts/generate-trending-status");
          if (!s.running) {
            window.clearInterval(pollId);
            if (s.error) {
              toast.error("Falló trending", {
                id: toastId,
                description: s.error.slice(0, 200),
              });
            } else {
              toast.success(
                `${s.created} posts · ${s.images_done} imágenes generadas`,
                {
                  id: toastId,
                  description: `${s.stories_found} noticias procesadas.`,
                  icon: <Flame className="h-4 w-4" />,
                  duration: 8000,
                },
              );
            }
            posts.refetch();
          } else {
            toast.loading(
              `Trending… ${s.created}/${s.stories_found || s.requested} posts · ${s.images_done} imgs`,
              { id: toastId },
            );
          }
        } catch {
          /* keep polling */
        }
      }, 4000);
    } catch (e) {
      toast.error("No se pudo lanzar trending", {
        id: toastId,
        description: String(e).slice(0, 160),
      });
    }
  };

  return (
    <div className="space-y-5">
      {/* Header con métricas + botones */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <Card variant="glass" hover="lift" className="p-4">
          <div className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Drafts trending
          </div>
          <div className="mt-2 mono text-2xl font-semibold tabular-nums leading-none text-[hsl(var(--accent-1))]">
            {drafts.length}
          </div>
          <div className="mt-1 text-[10px] text-muted-foreground">
            listos para revisar y programar
          </div>
        </Card>
        <Card variant="glass" hover="lift" className="p-4">
          <div className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Programados
          </div>
          <div className="mt-2 mono text-2xl font-semibold tabular-nums leading-none text-foreground">
            {scheduled.length}
          </div>
          <div className="mt-1 text-[10px] text-muted-foreground">
            en cola para publicar
          </div>
        </Card>
        <Card variant="glass" hover="lift" className="p-4">
          <div className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Publicados
          </div>
          <div className="mt-2 mono text-2xl font-semibold tabular-nums leading-none text-foreground">
            {published.length}
          </div>
          <div className="mt-1 text-[10px] text-muted-foreground">
            histórico
          </div>
        </Card>
      </div>

      {/* Controles de generación */}
      <Card variant="glass">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="inline-flex items-center gap-2">
              <Flame className="h-4 w-4 text-[hsl(var(--accent-2))]" />
              Trending news · últimas 24h
            </CardTitle>
            <p className="text-[11px] text-muted-foreground mt-1">
              Scraping HN + dev.to, un post por noticia con Claude y banner
              AMD-style con la og:image del artículo.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 flex-wrap">
            <select
              value={postLang}
              onChange={(e) => setPostLang(e.target.value as "es" | "en")}
              className="h-8 rounded-md border border-[hsl(var(--border))] bg-transparent px-2 text-xs"
            >
              <option value="es">Español</option>
              <option value="en">English</option>
            </select>
            <Button
              size="sm"
              onClick={() => generateTrending({ count: 10, replace: false })}
              shimmer
            >
              <Flame className="h-3.5 w-3.5" />
              Trending +10
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="border-pink-500/40 text-pink-300 hover:bg-pink-500/10"
              onClick={() => generateTrending({ count: 15, replace: true })}
            >
              <RefreshCcw className="h-3.5 w-3.5" />
              Regenerar (borra drafts antiguos)
            </Button>
          </div>
        </CardHeader>
      </Card>

      {/* Grid de trending drafts */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="inline-flex items-center gap-2">
            <Flame className="h-4 w-4 text-[hsl(var(--accent-1))]" />
            Drafts listos
          </CardTitle>
          <p className="text-[11px] text-muted-foreground">
            Ordenados del más reciente al más antiguo. Click en cada tarjeta
            para revisar/editar antes de programar.
          </p>
        </CardHeader>
        <CardContent>
          {posts.isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {[...Array(6)].map((_, i) => (
                <Skeleton key={i} className="h-64 w-full" />
              ))}
            </div>
          ) : drafts.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[hsl(var(--border))] p-10 text-center space-y-3">
              <p className="text-sm text-muted-foreground">
                No hay drafts trending. Dale a “Trending +10” para generar.
              </p>
              <Button
                onClick={() => generateTrending({ count: 10, replace: false })}
                shimmer
              >
                <Flame className="h-3.5 w-3.5" />
                Traer top 10 noticias
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {drafts.map((p) => (
                <div key={p.id} className="space-y-2">
                  <PostCard post={p} />
                  {p.source_url && (
                    <a
                      href={p.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-[hsl(var(--accent-1))] mono"
                    >
                      <ExternalLink className="h-3 w-3" />
                      fuente
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
