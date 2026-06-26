"use client";

import { Calendar, Heart, MessageCircle, Repeat2, Send, Image as ImageIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cn, formatShort } from "@/lib/utils";
import type { Post } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function PostCard({
  post,
  onClick,
  variant = "preview",
}: {
  post: Post;
  onClick?: () => void;
  variant?: "preview" | "compact";
}) {
  if (variant === "compact") {
    return (
      <Card
        variant="solid"
        hover={onClick ? "lift" : "none"}
        className={cn("p-3", onClick && "cursor-pointer")}
        onClick={onClick}
      >
        <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1">
          <span className="inline-flex items-center gap-1 mono">
            <Calendar className="h-3 w-3" />
            {formatShort(post.date)}
          </span>
          <Badge
            variant={post.status === "scheduled" ? "default" : "secondary"}
            size="sm"
          >
            {post.status}
          </Badge>
        </div>
        <div className="text-sm font-medium leading-snug line-clamp-2 font-[family-name:var(--font-display)]">
          {post.topic}
        </div>
      </Card>
    );
  }

  // Phone-mock LinkedIn preview with image thumbnail
  return (
    <Card
      variant="glass"
      hover={onClick ? "lift" : "none"}
      className={cn("overflow-hidden", onClick && "cursor-pointer")}
      onClick={onClick}
    >
      {/* Image thumbnail at top */}
      <div className="aspect-[1200/900] w-full bg-[hsl(var(--surface))]/40 relative overflow-hidden border-b border-[hsl(var(--border))]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`${API_BASE}/posts/${post.id}/image`}
          alt={post.topic}
          loading="lazy"
          className="absolute inset-0 h-full w-full object-cover"
          onError={(e) => {
            const t = e.target as HTMLImageElement;
            t.style.display = "none";
            t.parentElement?.classList.add("no-image");
          }}
        />
        <div className="absolute inset-0 grid place-items-center text-muted-foreground/40 pointer-events-none [.no-image_&]:opacity-100 opacity-0 transition-opacity">
          <div className="flex flex-col items-center gap-1 text-[10px]">
            <ImageIcon className="h-5 w-5" />
            <span>Sin imagen aún</span>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-[hsl(var(--accent-1))] to-[hsl(var(--accent-2))] text-[hsl(var(--primary-foreground))] text-[10px] font-bold mono">
              YN
            </div>
            <div className="leading-tight">
              <div className="text-[11px] font-semibold">Your Name</div>
              <div className="text-[9px] text-muted-foreground inline-flex items-center gap-1 mono">
                <Calendar className="h-2.5 w-2.5" />
                {formatShort(post.date)}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            {post.kind === "trending" && (
              <Badge
                size="sm"
                className="bg-orange-500/15 text-orange-300 border border-orange-500/40"
              >
                🔥 trending
              </Badge>
            )}
            <Badge
              variant={post.status === "scheduled" ? "default" : "secondary"}
              size="sm"
            >
              {post.status}
            </Badge>
          </div>
        </div>

        <div className="text-sm font-medium leading-snug line-clamp-2 font-[family-name:var(--font-display)]">
          {post.topic}
        </div>
        <p className="text-xs text-muted-foreground line-clamp-2 whitespace-pre-line leading-relaxed">
          {post.content.replace(/^#.*\n/, "")}
        </p>
        <div className="flex flex-wrap gap-1">
          {post.hashtags.slice(0, 4).map((h) => (
            <span
              key={h}
              className="text-[10px] text-[hsl(var(--accent-1))]/80 mono"
            >
              {h}
            </span>
          ))}
        </div>

        <div className="flex items-center gap-4 border-t border-[hsl(var(--border))] pt-2 text-[10px] text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Heart className="h-3 w-3" /> 0
          </span>
          <span className="inline-flex items-center gap-1">
            <MessageCircle className="h-3 w-3" /> 0
          </span>
          <span className="inline-flex items-center gap-1">
            <Repeat2 className="h-3 w-3" /> 0
          </span>
          <span className="ml-auto inline-flex items-center gap-1">
            <Send className="h-3 w-3" /> {post.status}
          </span>
        </div>
      </div>
    </Card>
  );
}
