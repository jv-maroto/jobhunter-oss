// Cliente de integraciones (Gmail tracking, Pilar 4).
import { api } from "@/lib/api";

export interface GmailStatus {
  enabled: boolean;
  mode: string | null;
  account: string;
  connected: boolean;
  scope: string;
  last_sync_at: string | null;
}

export interface EmailEvent {
  id: number;
  type: string;
  company: string | null;
  from_name: string;
  from_email: string;
  subject: string;
  snippet: string;
  received_at: string | null;
  job_id: number | null;
  status: string;
  match_method: string;
  match_confidence: number;
  applied_status_change: string | null;
  summary_es: string;
  next_action_es: string;
}

export interface SyncResult {
  connected: boolean;
  fetched: number;
  processed: number;
  applied: number;
  pending_review: number;
}

export const EVENT_TYPE_LABEL: Record<string, string> = {
  rechazo: "Rechazo",
  invitacion_entrevista: "Entrevista",
  oferta: "Oferta",
  peticion_info: "Piden info",
  acuse_recibo: "Acuse recibo",
  irrelevante: "Irrelevante",
};

export const EVENT_TYPE_COLOR: Record<string, string> = {
  rechazo: "text-rose-400 border-rose-400/40",
  invitacion_entrevista: "text-emerald-400 border-emerald-400/40",
  oferta: "text-amber-400 border-amber-400/40",
  peticion_info: "text-sky-400 border-sky-400/40",
  acuse_recibo: "text-muted-foreground border-[hsl(var(--border))]",
};

export const integrationsApi = {
  status: () => api<GmailStatus>("/integrations/gmail/status"),
  connectImap: (email: string, app_password: string) =>
    api<GmailStatus>("/integrations/gmail/connect", {
      method: "POST",
      body: JSON.stringify({ mode: "imap", email, app_password }),
    }),
  connectApi: (client_secret: unknown) =>
    api<GmailStatus>("/integrations/gmail/connect", {
      method: "POST",
      body: JSON.stringify({ mode: "api", client_secret }),
    }),
  disconnect: () => api<{ ok: boolean }>("/integrations/gmail/disconnect", { method: "POST" }),
  sync: () => api<SyncResult>("/integrations/gmail/sync", { method: "POST" }),
  listEvents: () => api<EmailEvent[]>("/email-events"),
  applyEvent: (id: number) => api<EmailEvent>(`/email-events/${id}/apply`, { method: "POST" }),
  dismissEvent: (id: number) => api<EmailEvent>(`/email-events/${id}/dismiss`, { method: "POST" }),
  undoEvent: (id: number) => api<EmailEvent>(`/email-events/${id}/undo`, { method: "POST" }),
};
