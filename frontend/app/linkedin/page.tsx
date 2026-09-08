"use client";

import {
  ContactRound,
  ExternalLink,
  MessageSquare,
  Calendar,
  Copy,
  RefreshCcw,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { WeekScheduler } from "@/components/posts/WeekScheduler";
import { PersonCard } from "@/components/persons/PersonCard";
import { usePosts } from "@/hooks/usePosts";
import { usePersons } from "@/hooks/usePersons";
import * as React from "react";
import { Input, Textarea } from "@/components/ui/input";
import {
  useAddManualPost,
  useCommentSuggestions,
  useMarkCommented,
  useRegenerateComment,
  useSkipComment,
} from "@/hooks/useComments";

export default function LinkedInPage() {
  const posts = usePosts();
  const persons = usePersons();
  const comments = useCommentSuggestions(8);
  const regenerate = useRegenerateComment();
  const markCommented = useMarkCommented();
  const skipComment = useSkipComment();

  const pendingPersons = (persons.data ?? []).filter((p) => p.status === "pending");
  const commentsList = comments.data ?? [];

  const addManual = useAddManualPost();
  const [manualUrl, setManualUrl] = React.useState("");
  const [manualAuthor, setManualAuthor] = React.useState("");
  const [manualContent, setManualContent] = React.useState("");

  const submitManual = async () => {
    if (!manualUrl || !manualContent) {
      toast.error("URL y contenido del post son obligatorios");
      return;
    }
    try {
      await addManual.mutateAsync({
        post_url: manualUrl,
        author_name: manualAuthor || "Unknown",
        content_excerpt: manualContent,
      });
      toast.success("Post añadido. Claude generó comentario.");
      setManualUrl("");
      setManualAuthor("");
      setManualContent("");
    } catch (e) {
      toast.error("Failed", { description: String(e).slice(0, 120) });
    }
  };

  return (
    <div className="space-y-5">
      {/* MIDI 3-panel header */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <Card variant="glass" hover="lift" className="p-4">
          <div className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Posts queue
          </div>
          <div className="mt-2 mono text-2xl font-semibold tabular-nums leading-none text-foreground">
            {(posts.data ?? []).length}
          </div>
          <div className="mt-1 text-[10px] text-muted-foreground">
            this week
          </div>
        </Card>
        <Card variant="glass" hover="lift" className="p-4">
          <div className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Connection requests
          </div>
          <div className="mt-2 mono text-2xl font-semibold tabular-nums leading-none text-[hsl(var(--accent-1))]">
            {pendingPersons.length}
          </div>
          <div className="mt-1 text-[10px] text-muted-foreground">
            pending outreach
          </div>
        </Card>
        <Card variant="glass" hover="lift" className="p-4">
          <div className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Comments
          </div>
          <div className="mt-2 mono text-2xl font-semibold tabular-nums leading-none text-foreground">
            {commentsList.length}
          </div>
          <div className="mt-1 text-[10px] text-muted-foreground">
            suggested
          </div>
        </Card>
      </div>

      {/* Posts — week scheduler */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="inline-flex items-center gap-2">
            <Calendar className="h-4 w-4 text-[hsl(var(--accent-1))]" />
            This week of posts
          </CardTitle>
          <p className="text-[11px] text-muted-foreground">
            Click any card to edit before scheduling.
          </p>
        </CardHeader>
        <CardContent>
          {posts.isLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <WeekScheduler posts={posts.data ?? []} />
          )}
        </CardContent>
      </Card>

      {/* Connections + Comments side by side */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="inline-flex items-center gap-2">
              <ContactRound className="h-4 w-4 text-[hsl(var(--accent-1))]" />
              Connections queue
            </CardTitle>
            <p className="text-[11px] text-muted-foreground">
              Prioritised by match relevance.
            </p>
          </CardHeader>
          <CardContent>
            {persons.isLoading ? (
              <Skeleton className="h-48 w-full" />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {(persons.data ?? []).map((p) => (
                  <PersonCard key={p.id} person={p} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardHeader>
            <CardTitle className="inline-flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-[hsl(var(--accent-2))]" />
              Comment suggestions
            </CardTitle>
            <p className="text-[11px] text-muted-foreground">
              Pega abajo la URL y contenido de un post de LinkedIn donde quieras
              comentar. Claude generará un comentario contextual.
            </p>
          </CardHeader>
          <CardContent className="border-b border-[hsl(var(--border))] space-y-2 pb-4">
            <Input
              placeholder="URL del post: https://www.linkedin.com/posts/..."
              value={manualUrl}
              onChange={(e) => setManualUrl(e.target.value)}
              className="text-xs"
            />
            <Input
              placeholder="Nombre del autor (opcional)"
              value={manualAuthor}
              onChange={(e) => setManualAuthor(e.target.value)}
              className="text-xs"
            />
            <Textarea
              placeholder="Pega el contenido del post (primeras 5-10 líneas)"
              value={manualContent}
              onChange={(e) => setManualContent(e.target.value)}
              rows={4}
              className="text-xs"
            />
            <Button
              size="sm"
              shimmer
              onClick={submitManual}
              disabled={addManual.isPending}
              className="w-full"
            >
              <MessageSquare className="h-3.5 w-3.5" />
              Generar comentario con Claude
            </Button>
          </CardContent>
          <CardContent className="space-y-3">
            {comments.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : commentsList.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[hsl(var(--border))] p-6 text-center space-y-2 text-xs">
                <p className="text-muted-foreground">
                  No comment suggestions yet. To populate this list:
                </p>
                <ol className="text-left text-muted-foreground/80 max-w-md mx-auto list-decimal pl-5 space-y-1">
                  <li>Make sure the JobHunter extension is loaded in your browser.</li>
                  <li>
                    Open <span className="mono">linkedin.com/feed</span> and
                    scroll through a few posts.
                  </li>
                  <li>
                    The extension captures posts and the backend generates a
                    comment draft with Claude. Refresh this page.
                  </li>
                </ol>
              </div>
            ) : (
              commentsList.map((c) => (
                <Card
                  key={c.id}
                  variant="solid"
                  hover="lift"
                  className="p-4 space-y-2"
                >
                  <div className="flex items-center justify-between text-xs">
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">
                        {c.author_name ?? "Unknown"}
                      </div>
                      {c.author_headline && (
                        <div className="text-[10px] text-muted-foreground truncate">
                          {c.author_headline}
                        </div>
                      )}
                    </div>
                    <a
                      href={c.post_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-muted-foreground hover:text-[hsl(var(--accent-1))] inline-flex items-center gap-1 text-[10px] shrink-0 ml-2"
                    >
                      Post <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                  {c.content_excerpt && (
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      {c.content_excerpt}
                    </p>
                  )}
                  <div className="rounded-md border border-[hsl(var(--border))] bg-white/[0.02] p-2.5 text-xs leading-relaxed whitespace-pre-line">
                    {c.suggested_comment ?? "(no draft yet)"}
                  </div>
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-1.5">
                      <Badge variant="mono" size="sm">
                        score {Math.round(c.relevance_score * 100)}
                      </Badge>
                      <Badge variant="outline" size="sm">
                        {c.status}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={async () => {
                          try {
                            await regenerate.mutateAsync(c.id);
                            toast.success("Comment regenerated");
                          } catch {
                            toast.error("Regenerate failed");
                          }
                        }}
                        title="Regenerate with Claude"
                      >
                        <RefreshCcw className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={async () => {
                          try {
                            await skipComment.mutateAsync(c.id);
                          } catch {
                            /* noop */
                          }
                        }}
                        title="Skip this one"
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="sm"
                        shimmer
                        onClick={async () => {
                          if (c.suggested_comment) {
                            try {
                              await navigator.clipboard.writeText(c.suggested_comment);
                              toast.success("Comment copied + post opened", {
                                icon: <Copy className="h-4 w-4" />,
                              });
                            } catch {
                              toast.error("Copy failed");
                            }
                          }
                          window.open(c.post_url, "_blank");
                          try {
                            await markCommented.mutateAsync(c.id);
                          } catch {
                            /* noop */
                          }
                        }}
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                        Copy & Open
                      </Button>
                    </div>
                  </div>
                </Card>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
