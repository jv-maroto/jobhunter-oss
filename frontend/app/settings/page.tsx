"use client";

import * as React from "react";
import Link from "next/link";
import { useTheme } from "next-themes";
import { Save, Bot, Palette, FileJson } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";

// Shown only if the backend can't load cv_master.json (first-time setup).
// Edit this through the UI below, or directly in backend/app/data/cv_master.json.
const DEFAULT_CV: Record<string, unknown> = {
  personal: {
    name: "Your Full Name",
    title: "Your Professional Title",
    email: "you@example.com",
    phone: "+34 600 000 000",
    location: "City, Country",
    github: "https://github.com/your-handle",
    linkedin: "https://linkedin.com/in/your-handle",
    portfolio: "https://your-handle.github.io/portfolio",
  },
  summary_es: "Resumen profesional en español, 2-3 frases.",
  summary_en: "Professional summary in English, 2-3 sentences.",
  languages: [
    { name: "English", level: "B2" },
  ],
  skills: {
    backend: ["Python", "FastAPI"],
    frontend: ["React", "TypeScript"],
    databases: ["PostgreSQL"],
    devops: ["Docker"],
  },
  search_preferences: {
    salary_min_eur: 30000,
    salary_max_eur: 50000,
    remote_only: false,
    preferred_countries: ["ES", "EU", "Remote"],
  },
};

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [cv, setCv] = React.useState<string>(
    JSON.stringify(DEFAULT_CV, null, 2),
  );
  const [loaded, setLoaded] = React.useState(false);

  React.useEffect(() => {
    (async () => {
      try {
        const remote = await api<Record<string, unknown>>("/settings/cv_master");
        setCv(JSON.stringify(remote, null, 2));
      } catch {
        // backend offline — usamos default
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const saveCv = async () => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(cv);
    } catch (e) {
      toast.error("CV JSON inválido", { description: String(e) });
      return;
    }
    try {
      await api("/settings/cv_master", {
        method: "PUT",
        body: JSON.stringify(parsed),
      });
      toast.success("cv_master.json guardado");
    } catch {
      toast.warning("Backend offline — cambios no persistidos");
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="inline-flex items-center gap-2">
            <Bot className="h-4 w-4 text-[hsl(var(--accent-1))]" />
            IA y claves
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Elige proveedor (Anthropic / OpenAI / Gemini), IA local con Ollama (gratis) o
            sin IA, y gestiona tus API keys desde la pantalla de IA.
          </p>
          <Link href="/settings/ai">
            <Button variant="outline">Ir a Ajustes de IA →</Button>
          </Link>
        </CardContent>
      </Card>

      <Card variant="glass">
        <CardHeader>
          <CardTitle className="inline-flex items-center gap-2">
            <Palette className="h-4 w-4 text-[hsl(var(--accent-2))]" />
            Appearance
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">Dark mode</div>
              <div className="text-[11px] text-muted-foreground">
                Tema oscuro estilo Command Center por defecto.
              </div>
            </div>
            <Switch
              checked={theme === "dark"}
              onCheckedChange={(v) => setTheme(v ? "dark" : "light")}
            />
          </div>
          <div className="rounded-md border border-[hsl(var(--border))] bg-white/[0.02] p-3">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">
              Accent palette
            </div>
            <div className="flex items-center gap-2">
              <span className="h-6 w-6 rounded-md bg-[hsl(var(--accent-1))]" />
              <span className="h-6 w-6 rounded-md bg-[hsl(var(--accent-2))]" />
              <span className="h-6 w-6 rounded-md bg-[hsl(var(--accent-warn))]" />
              <span className="h-6 w-6 rounded-md bg-gradient-to-br from-[hsl(var(--accent-1))] to-[hsl(var(--accent-2))]" />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card variant="glass" className="lg:col-span-2">
        <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
          <div>
            <CardTitle className="inline-flex items-center gap-2">
              <FileJson className="h-4 w-4 text-[hsl(var(--accent-1))]" />
              cv_master.json
            </CardTitle>
            <p className="text-[11px] text-muted-foreground mt-1">
              Fuente de verdad para generar CVs personalizados con Claude.
              {loaded ? "" : " · Cargando…"}
            </p>
          </div>
          <Button onClick={saveCv} shimmer>
            <Save />
            Save
          </Button>
        </CardHeader>
        <CardContent>
          <Textarea
            value={cv}
            onChange={(e) => setCv(e.target.value)}
            rows={24}
            className="font-mono text-xs"
            spellCheck={false}
          />
        </CardContent>
      </Card>
    </div>
  );
}
