"use client";

import * as React from "react";
import { CalendarClock, CheckCircle2, Download, FileText, Image as ImageIcon, RefreshCcw, Send } from "lucide-react";
import { formatShort } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { PostCard } from "@/components/posts/PostCard";
import { useMarkPostPublished, useSchedulePost } from "@/hooks/usePosts";
import { api } from "@/lib/api";
import { toast } from "sonner";
import type { Post } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function defaultSlot(): string {
  // Mañana a las 09:00 hora local — formato `YYYY-MM-DDTHH:mm`
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(9, 0, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function WeekScheduler({ posts }: { posts: Post[] }) {
  const [active, setActive] = React.useState<Post | null>(null);
  const [draft, setDraft] = React.useState("");
  const [when, setWhen] = React.useState<string>(defaultSlot());
  const [imageBust, setImageBust] = React.useState(0);
  const [regenerating, setRegenerating] = React.useState(false);
  const schedule = useSchedulePost();
  const markPublished = useMarkPostPublished();

  const downloadImage = (postId: number) => {
    // Backend sets Content-Disposition: attachment so the browser downloads
    // without leaving the page or showing a tab.
    const url = `${API_BASE}/posts/${postId}/image?download=1&bust=${imageBust}`;
    const a = document.createElement("a");
    a.href = url;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
    toast.success("Descargando imagen…", {
      description: "Mira la barra de descargas.",
      icon: <Download className="h-4 w-4" />,
    });
  };

  const regenerateImage = async (postId: number) => {
    setRegenerating(true);
    try {
      await api(`/posts/${postId}/generate-image`, { method: "POST" });
      setImageBust(Date.now());
      toast.success("Imagen regenerada");
    } catch (e) {
      const msg = String(e);
      if (msg.includes("404") || msg.includes("Post not found")) {
        toast.error(`Post ${postId} ya no existe en la base de datos`, {
          description: "Refrescando lista…",
        });
        // The post we have in cache is stale → refresh via the parent query
        if (typeof window !== "undefined") {
          window.location.reload();
        }
      } else {
        toast.error(`Fallo al regenerar imagen (post ${postId})`, {
          description: msg.slice(0, 140),
        });
      }
    } finally {
      setRegenerating(false);
    }
  };

  const openPost = React.useCallback((p: Post) => {
    setDraft(p.content);
    if (p.scheduled_at) {
      // datetime-local format
      const d = new Date(p.scheduled_at);
      const pad = (n: number) => String(n).padStart(2, "0");
      setWhen(
        `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`,
      );
    } else {
      setWhen(defaultSlot());
    }
    setActive(p);
  }, []);

  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {posts.map((p) => (
          <PostCard key={p.id} post={p} onClick={() => openPost(p)} />
        ))}
      </div>

      <Dialog
        open={!!active}
        onOpenChange={(open) => !open && setActive(null)}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="inline-flex items-center gap-2">
              <FileText className="h-4 w-4 text-[hsl(var(--accent-1))]" />
              {active
                ? `${active.topic} · ${formatShort(active.date)}`
                : ""}
            </DialogTitle>
            {active?.status === "scheduled" && (
              <p className="text-[11px] text-[hsl(var(--accent-1))] inline-flex items-center gap-1">
                <CalendarClock className="h-3 w-3" />
                Already scheduled — re-saving will update the slot.
              </p>
            )}
          </DialogHeader>
          <div className="space-y-3">
            {/* Image preview + actions */}
            {active && (
              <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--surface))]/60 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase tracking-wider text-muted-foreground inline-flex items-center gap-1">
                    <ImageIcon className="h-3 w-3" />
                    Imagen generada
                  </span>
                  <div className="flex gap-1.5">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => regenerateImage(active.id)}
                      disabled={regenerating}
                      title="Regenerar imagen con Pillow"
                    >
                      <RefreshCcw
                        className={
                          regenerating ? "h-3 w-3 animate-spin" : "h-3 w-3"
                        }
                      />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => downloadImage(active.id)}
                      title="Descargar imagen como PNG"
                    >
                      <Download className="h-3 w-3" />
                      Descargar imagen
                    </Button>
                  </div>
                </div>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`${API_BASE}/posts/${active.id}/image?bust=${imageBust}`}
                  alt={active.topic}
                  className="w-full rounded-md border border-[hsl(var(--border))]"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
              </div>
            )}
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
                Content
              </label>
              <Textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={10}
                className="font-mono text-xs"
              />
            </div>
            <div className="grid grid-cols-[1fr_auto] items-end gap-2">
              <div>
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Schedule for
                </label>
                <Input
                  type="datetime-local"
                  value={when}
                  onChange={(e) => setWhen(e.target.value)}
                  className="text-xs"
                />
              </div>
              <span className="text-[10px] text-muted-foreground mono pb-2">
                local time
              </span>
            </div>
            {active?.hashtags && active.hashtags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {active.hashtags.map((h) => (
                  <span
                    key={h}
                    className="text-[10px] text-[hsl(var(--accent-1))]/80 mono"
                  >
                    {h}
                  </span>
                ))}
              </div>
            )}
          </div>
          <DialogFooter className="flex-wrap gap-2">
            <Button variant="outline" onClick={() => setActive(null)}>
              Cancel
            </Button>
            {active?.status !== "published" && (
              <Button
                variant="outline"
                disabled={markPublished.isPending}
                onClick={async () => {
                  if (!active) return;
                  try {
                    await markPublished.mutateAsync(active.id);
                    toast.success("Marcado como publicado", {
                      description:
                        "Este tema ya no se propondrá al generar la próxima semana.",
                      icon: <CheckCircle2 className="h-4 w-4" />,
                    });
                    setActive(null);
                  } catch (e) {
                    toast.error("No se pudo marcar como publicado", {
                      description: String(e).slice(0, 140),
                    });
                  }
                }}
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                Marcar publicado
              </Button>
            )}
            <Button
              shimmer
              disabled={schedule.isPending}
              onClick={async () => {
                if (!active) return;
                try {
                  const whenIso = new Date(when).toISOString();
                  await schedule.mutateAsync({
                    id: active.id,
                    when: whenIso,
                  });
                  // Copy content to clipboard so the user can paste it directly
                  // into LinkedIn's native post composer.
                  const hashtags = (active.hashtags ?? [])
                    .map((h) => (h.startsWith("#") ? h : `#${h}`))
                    .join(" ");
                  const textToCopy =
                    draft + (hashtags ? `\n\n${hashtags}` : "");
                  try {
                    await navigator.clipboard.writeText(textToCopy);
                  } catch {
                    /* ignore clipboard errors */
                  }
                  window.open(
                    "https://www.linkedin.com/feed/",
                    "_blank",
                    "noopener,noreferrer",
                  );
                  toast.success(`Copiado al portapapeles`, {
                    description:
                      "LinkedIn abierto. Pulsa 'Empezar publicación', pega (Cmd+V) y programa con el reloj.",
                    icon: <CalendarClock className="h-4 w-4" />,
                    duration: 8000,
                  });
                  setActive(null);
                } catch {
                  toast.error("Failed to schedule post");
                }
              }}
            >
              <Send />
              Copy & Open LinkedIn
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
