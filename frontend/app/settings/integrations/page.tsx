"use client";

import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { EVENT_TYPE_COLOR, EVENT_TYPE_LABEL, type EmailEvent } from "@/lib/integrations";
import { useEmailEvents, useGmailMutations, useGmailStatus } from "@/hooks/useGmail";

export default function IntegrationsPage() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold">Integraciones</h1>
        <p className="text-sm text-muted-foreground">
          Conecta Gmail para detectar rechazos/respuestas y mover el pipeline solo. Solo lectura,
          nunca borra nada, todo reversible.
        </p>
      </div>
      <GmailCard />
      <EmailEvents />
    </div>
  );
}

function GmailCard() {
  const { data: status } = useGmailStatus();
  const { connectImap, disconnect, sync } = useGmailMutations();
  const [email, setEmail] = React.useState("");
  const [pwd, setPwd] = React.useState("");

  const connected = status?.connected;

  const [connectError, setConnectError] = React.useState<string>("");
  async function doConnect() {
    setConnectError("");
    if (!email || !pwd) {
      toast.error("Email y app-password requeridos");
      return;
    }
    // Strip any spaces the user may have pasted from Google's UI
    const cleanPwd = pwd.replace(/\s+/g, "");
    try {
      await connectImap.mutateAsync({ email, app_password: cleanPwd });
      toast.success("Gmail conectado");
      setPwd("");
      setConnectError("");
    } catch (e) {
      // The backend now returns a human-readable diagnostic in `detail`.
      const detail = String(
        (e as { detail?: string; message?: string })?.detail
        ?? (e as Error)?.message
        ?? "",
      );
      setConnectError(detail || "No se pudo conectar. Revisa el app-password y que la 2FA esté activada.");
      toast.error("No se pudo conectar a Gmail");
    }
  }

  async function doSync() {
    try {
      const r = await sync.mutateAsync();
      toast.success(`Sync: ${r.fetched} leídos · ${r.applied} aplicados · ${r.pending_review} a revisar`);
    } catch {
      toast.error("El sync falló");
    }
  }

  return (
    <Card variant="solid">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Gmail
          {connected && <span className="text-xs text-emerald-400">● conectado</span>}
        </CardTitle>
        <CardDescription>
          {connected
            ? `${status?.account} · scope ${status?.scope}`
            : "Conecta con una contraseña de aplicación (requiere verificación en 2 pasos)."}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {connected ? (
          <>
            <p className="text-xs text-muted-foreground">
              Última sync: {status?.last_sync_at ? new Date(status.last_sync_at).toLocaleString("es-ES") : "nunca"}
            </p>
            <div className="flex gap-2">
              <Button variant="solid" onClick={doSync} disabled={sync.isPending}>
                {sync.isPending ? "Sincronizando…" : "Sincronizar ahora"}
              </Button>
              <Button
                variant="destructive"
                onClick={async () => {
                  await disconnect.mutateAsync();
                  toast.success("Gmail desconectado");
                }}
              >
                Desconectar
              </Button>
            </div>
          </>
        ) : (
          <>
            <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs space-y-2">
              <div className="font-semibold text-amber-200">
                Cómo generar el App Password (Google lo pide desde 2022)
              </div>
              <ol className="list-decimal pl-5 text-amber-100/90 space-y-1">
                <li>
                  Activa la <b>Verificación en 2 pasos</b> en{" "}
                  <a
                    href="https://myaccount.google.com/signinoptions/two-step-verification"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline hover:text-amber-100"
                  >
                    myaccount.google.com
                  </a>{" "}
                  si aún no está activa.
                </li>
                <li>
                  Ve a{" "}
                  <a
                    href="https://myaccount.google.com/apppasswords"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline hover:text-amber-100"
                  >
                    myaccount.google.com/apppasswords
                  </a>{" "}
                  y crea una nueva con nombre &ldquo;JobHunter&rdquo;.
                </li>
                <li>
                  Google te da <b>16 caracteres con espacios</b> (formato{" "}
                  <span className="mono">xxxx xxxx xxxx xxxx</span>). Pégala aquí — el
                  formulario te quita los espacios automáticamente.
                </li>
                <li>
                  NO uses tu contraseña normal de Gmail — Google la rechazará.
                </li>
              </ol>
            </div>
            <Input
              placeholder="tu-email@gmail.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
            <Input
              type="password"
              placeholder="App Password (16 caracteres, con o sin espacios)"
              value={pwd}
              onChange={(e) => setPwd(e.target.value)}
              autoComplete="current-password"
            />
            <Button variant="solid" onClick={doConnect} disabled={connectImap.isPending}>
              {connectImap.isPending ? "Conectando…" : "Conectar Gmail"}
            </Button>
            {connectError && (
              <div className="rounded-md border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-100 whitespace-pre-line">
                {connectError}
              </div>
            )}
            <p className="text-[10px] text-muted-foreground">
              Solo se leen correos relevantes (recruiters, ATS). Nunca se borran ni modifican.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function EmailEvents() {
  const { data: events, isLoading } = useEmailEvents();
  const { applyEvent, dismissEvent, undoEvent } = useGmailMutations();

  if (isLoading) return <p className="text-sm text-muted-foreground">Cargando eventos…</p>;
  if (!events || events.length === 0) {
    return (
      <Card variant="solid">
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          Sin eventos todavía. Conecta Gmail y pulsa «Sincronizar ahora».
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {events.map((e) => (
        <EventRow
          key={e.id}
          e={e}
          onApply={() => applyEvent.mutate(e.id)}
          onDismiss={() => dismissEvent.mutate(e.id)}
          onUndo={() => undoEvent.mutate(e.id)}
        />
      ))}
    </div>
  );
}

function EventRow({
  e,
  onApply,
  onDismiss,
  onUndo,
}: {
  e: EmailEvent;
  onApply: () => void;
  onDismiss: () => void;
  onUndo: () => void;
}) {
  return (
    <Card variant="solid">
      <CardContent className="flex items-center justify-between gap-3 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "rounded border px-1.5 py-0.5 text-[10px] uppercase",
                EVENT_TYPE_COLOR[e.type] ?? "text-muted-foreground border-[hsl(var(--border))]",
              )}
            >
              {EVENT_TYPE_LABEL[e.type] ?? e.type}
            </span>
            <span className="truncate text-sm font-medium">{e.company || e.from_name}</span>
            {e.applied_status_change && (
              <span className="text-[10px] text-emerald-400">{e.applied_status_change}</span>
            )}
          </div>
          <p className="truncate text-xs text-muted-foreground">{e.summary_es || e.subject}</p>
        </div>
        <div className="flex shrink-0 gap-1.5">
          {e.status === "pending_review" && e.job_id && (
            <Button size="sm" variant="solid" onClick={onApply}>
              Aplicar
            </Button>
          )}
          {(e.status === "auto_applied" || e.status === "applied") && e.applied_status_change && (
            <Button size="sm" variant="ghost" onClick={onUndo}>
              Deshacer
            </Button>
          )}
          {e.status !== "dismissed" && (
            <Button size="sm" variant="ghost" onClick={onDismiss}>
              Descartar
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
