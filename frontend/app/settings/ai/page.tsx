"use client";

import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { AI_PROVIDERS, type AiMode, type AiProvider } from "@/lib/aiSettings";
import { useAiSettings, useTestAiSettings, useUpdateAiSettings } from "@/hooks/useAiSettings";

const MODES: { id: AiMode; label: string; desc: string }[] = [
  {
    id: "auto",
    label: "Automático (recomendado)",
    desc: "Usa la nube si hay clave, si no Ollama local. Degrada solo.",
  },
  {
    id: "cloud",
    label: "Cloud (con clave)",
    desc: "Mejor calidad. Requiere una clave de Anthropic, OpenAI o Gemini.",
  },
  {
    id: "local",
    label: "Local (Ollama, gratis)",
    desc: "Todo en tu máquina, sin coste ni nube. Requiere Ollama instalado.",
  },
  {
    id: "off",
    label: "Solo scraping (sin IA)",
    desc: "Desactiva la IA. Scoring y generación usan heurísticas.",
  },
];

export default function AiSettingsPage() {
  const { data, isLoading } = useAiSettings();
  const update = useUpdateAiSettings();
  const test = useTestAiSettings();

  const [mode, setMode] = React.useState<AiMode>("auto");
  const [provider, setProvider] = React.useState<AiProvider>("anthropic");
  const [keyInput, setKeyInput] = React.useState("");
  const [seeded, setSeeded] = React.useState(false);

  // Sembrar el estado local una vez con lo que viene del backend.
  React.useEffect(() => {
    if (!data || seeded) return;
    setMode(data.ai_mode);
    setProvider(data.ai_cloud_provider);
    setSeeded(true);
  }, [data, seeded]);

  if (isLoading || !data) {
    return <div className="text-sm text-muted-foreground">Cargando ajustes de IA…</div>;
  }

  const usesCloud = mode === "cloud" || mode === "auto";
  const providerHasKey = data.has_key?.[provider] ?? false;

  async function save() {
    const patch: Parameters<typeof update.mutateAsync>[0] = {
      ai_mode: mode,
      ai_cloud_provider: provider,
    };
    const trimmedKey = keyInput.trim();
    if (trimmedKey) {
      patch.keys = { [provider]: trimmedKey };
    }
    try {
      await update.mutateAsync(patch);
      setKeyInput(""); // nunca conservamos la clave en claro en el cliente
      toast.success("Ajustes de IA guardados");
    } catch {
      toast.error("No se pudo guardar (revisa el backend)");
    }
  }

  async function runTest() {
    try {
      const res = await test.mutateAsync();
      if (res.ok) toast.success(`IA OK · ${res.provider}`);
      else toast.error(`Falló (${res.provider}): ${res.error ?? "sin detalle"}`);
    } catch {
      toast.error("No se pudo probar la IA");
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold">Inteligencia Artificial</h1>
        <p className="text-sm text-muted-foreground">
          Elige cómo se ejecuta la IA (scoring, generación de mensajes y scraping inteligente). Las
          claves se guardan en tu máquina y nunca se muestran en claro.
        </p>
      </div>

      <Card variant="solid">
        <CardHeader>
          <CardTitle>Modo</CardTitle>
          <CardDescription>
            Activa: <span className="text-foreground">{data.active || "ninguno"}</span>
            {data.local_available
              ? data.local_model_available
                ? ` · Ollama detectado (${data.local_model})`
                : ` · Ollama detectado pero falta el modelo ${data.local_model} — ejecuta: ollama pull ${data.local_model}`
              : " · Ollama no detectado"}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {MODES.map((m) => (
            <button
              key={m.id}
              onClick={() => setMode(m.id)}
              className={cn(
                "flex flex-col items-start gap-0.5 rounded-md border px-3 py-2 text-left transition-colors",
                mode === m.id
                  ? "border-[hsl(var(--accent-1))]/55 bg-[hsl(var(--accent-1))]/10"
                  : "border-[hsl(var(--border))] hover:border-[hsl(var(--accent-1))]/40",
              )}
              aria-pressed={mode === m.id}
            >
              <span className="text-sm font-medium">{m.label}</span>
              <span className="text-xs text-muted-foreground">{m.desc}</span>
            </button>
          ))}
        </CardContent>
      </Card>

      {usesCloud && (
        <Card variant="solid">
          <CardHeader>
            <CardTitle>Proveedor cloud</CardTitle>
            <CardDescription>
              Elige un proveedor y pega su clave. Mostramos «configurada» cuando ya hay una guardada.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-wrap gap-2">
              {AI_PROVIDERS.map((p) => (
                <Chip key={p.id} active={provider === p.id} onClick={() => setProvider(p.id)}>
                  {p.label}
                  {data.has_key?.[p.id] && (
                    <span className="ml-1.5 text-[10px] text-emerald-400">● configurada</span>
                  )}
                </Chip>
              ))}
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs text-muted-foreground">
                Clave de {AI_PROVIDERS.find((p) => p.id === provider)?.label}
                {providerHasKey && (
                  <span className="ml-2 text-emerald-400">configurada — pega una nueva para reemplazar</span>
                )}
              </label>
              <Input
                type="password"
                autoComplete="off"
                placeholder={
                  providerHasKey
                    ? "•••••••••• (deja vacío para mantener la actual)"
                    : AI_PROVIDERS.find((p) => p.id === provider)?.keyPlaceholder
                }
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
              />
              <p className="text-[11px] text-muted-foreground">
                La clave se envía al backend y se guarda en data/integrations/ai.json. Nunca vuelve al
                navegador.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex items-center justify-between">
        <Button variant="outline" onClick={runTest} disabled={test.isPending}>
          {test.isPending ? "Probando…" : "Probar"}
        </Button>
        <Button variant="solid" onClick={save} disabled={update.isPending}>
          {update.isPending ? "Guardando…" : "Guardar"}
        </Button>
      </div>
    </div>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center rounded-full border px-3 py-1.5 text-sm transition-colors",
        active
          ? "border-[hsl(var(--accent-1))]/55 bg-[hsl(var(--accent-1))]/15 text-[hsl(var(--accent-1))]"
          : "border-[hsl(var(--border))] text-muted-foreground hover:text-foreground hover:border-[hsl(var(--accent-1))]/40",
      )}
    >
      {children}
    </button>
  );
}
