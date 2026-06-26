"use client";

import * as React from "react";
import { ChevronDown } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ConnectButton } from "@/components/persons/ConnectButton";
import { avatarFor } from "@/lib/utils";
import type { Person } from "@/lib/types";

export function PersonCard({ person }: { person: Person }) {
  const [open, setOpen] = React.useState(false);
  const avatar = React.useMemo(
    () => avatarFor(person.full_name, 80),
    [person.full_name],
  );

  return (
    <Card variant="glass" hover="lift">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start gap-3">
          <div className="relative h-10 w-10 shrink-0 overflow-hidden rounded-lg border border-[hsl(var(--border))] bg-white/[0.04]">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={avatar}
              alt={person.full_name}
              width={40}
              height={40}
              className="h-10 w-10"
            />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-medium truncate font-[family-name:var(--font-display)]">
                {person.full_name}
              </div>
              <Badge
                variant={person.priority >= 85 ? "default" : "secondary"}
                size="sm"
                className="mono normal-case tracking-normal shrink-0"
              >
                P{person.priority}
              </Badge>
            </div>
            <div className="text-xs text-muted-foreground truncate">
              {person.headline}
            </div>
            <div className="mt-1 text-[11px] italic text-muted-foreground/80 line-clamp-2">
              {person.reason}
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center justify-between rounded-md border border-[hsl(var(--border))] bg-white/[0.02] px-3 py-2 text-[11px] text-muted-foreground hover:text-foreground hover:border-[hsl(var(--accent-1))]/30 transition-colors"
        >
          <span>{open ? "Ocultar mensaje" : "Ver mensaje"}</span>
          <ChevronDown
            className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`}
          />
        </button>

        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              key="msg"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.22, ease: "easeOut" }}
              className="overflow-hidden"
            >
              <div className="rounded-md border border-[hsl(var(--border))] bg-white/[0.02] p-3 text-xs leading-relaxed whitespace-pre-line">
                {person.message}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex justify-end">
          <ConnectButton person={person} />
        </div>
      </CardContent>
    </Card>
  );
}
