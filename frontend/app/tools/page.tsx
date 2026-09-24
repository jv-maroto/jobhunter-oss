import Link from "next/link";

const GROUPS = [
  { title: "Seguimiento", items: [
    ["/today", "Resumen del día", "Actividad y tareas pendientes."],
    ["/pipeline", "Tablero de candidaturas", "Tus candidaturas organizadas por etapa."],
    ["/metrics", "Resultados", "Evolución de tu búsqueda."],
  ] },
  { title: "Empresas y contactos", items: [
    ["/companies", "Empresas", "Consulta las empresas de tus ofertas."],
    ["/networking", "Contactos", "Organiza tu red profesional."],
  ] },
  { title: "Búsqueda avanzada", items: [
    ["/campaigns", "Campañas", "Configura búsquedas específicas si las necesitas."],
    ["/boards", "Portales de empresas", "Gestiona las fuentes de ofertas."],
    ["/swipe", "Revisión rápida", "Revisa las ofertas una a una."],
    ["/settings/search", "Preferencias de búsqueda", "Ajusta tus criterios profesionales."],
  ] },
  { title: "Configuración", items: [
    ["/settings/ai", "Inteligencia artificial", "Configura los proveedores de IA."],
    ["/settings/integrations", "Correo e integraciones", "Gestiona tus conexiones."],
  ] },
];

export default function ToolsPage() {
  return <div className="space-y-6"><div><h1 className="text-xl font-semibold">Herramientas</h1><p className="mt-1 text-sm text-muted-foreground">Opciones adicionales para cuando las necesites.</p></div>
    <div className="grid gap-4 md:grid-cols-2">{GROUPS.map(group => <section key={group.title} className="rounded-xl border border-[hsl(var(--border))] p-4"><h2 className="mb-3 font-semibold">{group.title}</h2><div className="space-y-1">{group.items.map(([href,title,description]) => <Link key={href} href={href} className="block rounded-lg p-3 hover:bg-white/5"><span className="text-sm font-medium text-[hsl(var(--accent-1))]">{title}</span><p className="mt-1 text-xs text-muted-foreground">{description}</p></Link>)}</div></section>)}</div>
  </div>;
}
