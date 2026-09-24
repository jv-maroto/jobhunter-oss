"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ListChecks, FileText, MessageSquare, UserRound, Megaphone, Settings, MoreHorizontal, Command, Sparkles, KanbanSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { commandPaletteStore } from "@/components/layout/CommandPalette";

const PRIMARY = [
  { href: "/today", label: "Inicio", icon: Sparkles },
  { href: "/jobs", label: "Ofertas", icon: ListChecks },
  { href: "/pipeline", label: "Pipeline", icon: KanbanSquare },
  { href: "/applications", label: "Candidaturas", icon: FileText },
  { href: "/interviews", label: "Entrevistas", icon: MessageSquare },
  { href: "/profile", label: "Mi perfil", icon: UserRound },
  { href: "/linkedin", label: "LinkedIn", icon: Megaphone },
];
const SECONDARY = [
  { href: "/tools", label: "Herramientas", icon: MoreHorizontal },
  { href: "/settings", label: "Ajustes", icon: Settings },
];
const TOOL_ROUTES = ["/today", "/pipeline", "/companies", "/networking", "/metrics", "/campaigns", "/boards", "/swipe"];

export function Sidebar() {
  const pathname = usePathname();
  const active = (href: string) => pathname === href || pathname.startsWith(`${href}/`) || (href === "/tools" && TOOL_ROUTES.includes(pathname));
  const itemClass = "flex h-11 shrink-0 items-center gap-3 rounded-lg px-3 text-sm transition-colors";
  return <>
    <nav aria-label="Navegación principal móvil" className="relative z-40 flex gap-1 overflow-x-auto border-b border-[hsl(var(--border))] p-2 md:hidden">
      {[...PRIMARY, ...SECONDARY].map(({href,label,icon:Icon}) => <Link key={href} href={href} aria-current={active(href) ? "page" : undefined} className={cn("flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs", active(href) ? "bg-white/10 text-foreground" : "text-muted-foreground")}><Icon size={15} />{label}</Link>)}
    </nav>
    <aside className="group/sidebar fixed left-0 top-0 z-50 hidden h-screen flex-col p-2 md:flex">
      <div className="glass-strong flex h-full w-[60px] flex-col overflow-hidden rounded-2xl py-3 transition-[width] duration-200 group-hover/sidebar:w-[212px] group-focus-within/sidebar:w-[212px]">
        <Link href="/jobs" aria-label="Jobslave: ofertas" className={cn(itemClass, "mx-1 mb-3")}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.png" alt="" className="h-7 w-7 shrink-0 object-contain" /><span className="hidden font-semibold group-hover/sidebar:block group-focus-within/sidebar:block">Jobslave</span>
        </Link>
        <nav aria-label="Navegación principal" className="flex flex-col gap-1 px-1.5">
          {PRIMARY.map(({href,label,icon:Icon}) => <Link key={href} href={href} title={label} aria-label={label} aria-current={active(href) ? "page" : undefined} className={cn(itemClass, active(href) ? "bg-white/10 text-[hsl(var(--accent-1))]" : "text-muted-foreground hover:bg-white/5 hover:text-foreground")}><Icon className="h-4 w-4 shrink-0" /><span className="hidden whitespace-nowrap group-hover/sidebar:block group-focus-within/sidebar:block">{label}</span></Link>)}
        </nav>
        <nav aria-label="Herramientas y ajustes" className="mt-auto flex flex-col gap-1 border-t border-[hsl(var(--border))] px-1.5 pt-3">
          <button type="button" aria-label="Buscar una sección" title="Buscar una sección (⌘K)" onClick={() => commandPaletteStore.open()} className={cn(itemClass, "text-muted-foreground hover:bg-white/5")}><Command className="h-4 w-4 shrink-0" /><span className="hidden whitespace-nowrap group-hover/sidebar:block group-focus-within/sidebar:block">Buscar sección</span></button>
          {SECONDARY.map(({href,label,icon:Icon}) => <Link key={href} href={href} title={label} aria-label={label} aria-current={active(href) ? "page" : undefined} className={cn(itemClass, active(href) ? "bg-white/10 text-foreground" : "text-muted-foreground hover:bg-white/5")}><Icon className="h-4 w-4 shrink-0" /><span className="hidden whitespace-nowrap group-hover/sidebar:block group-focus-within/sidebar:block">{label}</span></Link>)}
        </nav>
      </div>
    </aside>
  </>;
}
