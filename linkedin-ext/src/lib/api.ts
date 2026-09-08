import { getSettings } from "./storage";
import {
  ConnectResult,
  ExtTasksResponse,
  InboxReport,
  InboxSuggestionsResponse
} from "./types";

async function backend(): Promise<string> {
  const s = await getSettings();
  return s.backend_url.replace(/\/+$/, "");
}

// -- Shared-secret auth for /ext/* endpoints ---------------------------------
// The backend generates a random token on first boot. We fetch it once (from
// /ext/token, which the backend leaves unprotected on purpose) and stash it in
// chrome.storage.local. Every subsequent request sends it in X-Extension-Token.
// On 401 we clear and refetch — covers the case where the backend was reset.

const TOKEN_KEY = "jobhunter_ext_token";

async function getStoredToken(): Promise<string | null> {
  try {
    const v = await chrome.storage.local.get(TOKEN_KEY);
    return (v?.[TOKEN_KEY] as string | undefined) ?? null;
  } catch {
    return null;
  }
}

async function fetchAndStoreToken(base: string): Promise<string | null> {
  try {
    const r = await fetch(`${base}/ext/token`, {
      headers: { Accept: "application/json" }
    });
    if (!r.ok) return null;
    const body = (await r.json()) as { token?: string };
    const token = body?.token;
    if (!token) return null;
    await chrome.storage.local.set({ [TOKEN_KEY]: token });
    return token;
  } catch {
    return null;
  }
}

async function ensureToken(base: string): Promise<string | null> {
  return (await getStoredToken()) ?? (await fetchAndStoreToken(base));
}

/** Backend fetch that carries the shared secret for /ext/* endpoints.
 *  Exported for consumers that don't use jsonFetch (service worker). */
export async function extFetch(
  base: string,
  path: string,
  init?: RequestInit
): Promise<Response> {
  const url = `${base}${path.startsWith("/") ? path : "/" + path}`;
  const isBootstrap = path === "/ext/token";
  const token = isBootstrap ? null : await ensureToken(base);
  const runOnce = async (): Promise<Response> =>
    fetch(url, {
      ...init,
      headers: {
        ...(init?.headers ?? {}),
        ...(token ? { "X-Extension-Token": token } : {})
      }
    });
  let res = await runOnce();
  if (res.status === 401 && !isBootstrap) {
    await chrome.storage.local.remove(TOKEN_KEY);
    await ensureToken(base);
    res = await runOnce();
  }
  return res;
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const base = await backend();
  const url = `${base}${path.startsWith("/") ? path : "/" + path}`;
  // /ext/token bootstraps itself — no header, no retry loop
  const isBootstrap = path === "/ext/token";
  const token = isBootstrap ? null : await ensureToken(base);
  const runOnce = async (): Promise<Response> =>
    fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(token ? { "X-Extension-Token": token } : {}),
        ...(init?.headers ?? {})
      }
    });
  let res = await runOnce();
  // Token might be stale (backend regenerated) — refetch once and retry.
  if (res.status === 401 && !isBootstrap) {
    await chrome.storage.local.remove(TOKEN_KEY);
    await ensureToken(base);
    res = await runOnce();
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${res.statusText} :: ${body}`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return (await res.json()) as T;
}

export interface ApplyQueueTask {
  queue_id: number;
  job_id: number;
  platform: string;
  apply_url: string;
  materials: { cv_path?: string; cover_letter_path?: string; language?: string };
  title: string;
  company: string;
}

export interface AppliedReport {
  job_id: number;
  platform?: string;
  apply_url?: string;
  status?: string;
  queue_id?: number;
  screening_answers?: Record<string, string>;
}

export const api = {
  async health(): Promise<boolean> {
    try {
      await jsonFetch("/health");
      return true;
    } catch {
      // Si /health no existe, probamos /ext/tasks como prueba de vida
      try {
        await jsonFetch("/ext/tasks");
        return true;
      } catch {
        return false;
      }
    }
  },

  getTasks(): Promise<ExtTasksResponse> {
    return jsonFetch<ExtTasksResponse>("/ext/tasks");
  },

  reportConnectResult(result: ConnectResult): Promise<void> {
    return jsonFetch<void>("/ext/connect-result", {
      method: "POST",
      body: JSON.stringify(result)
    });
  },

  reportInboxMessages(report: InboxReport): Promise<InboxSuggestionsResponse[]> {
    return jsonFetch<InboxSuggestionsResponse[]>("/ext/inbox-messages", {
      method: "POST",
      body: JSON.stringify(report)
    });
  },

  reportPostResult(result: {
    task_id?: string;
    post_id: number;
    success: boolean;
    error?: string;
    scheduled_at?: string;
  }): Promise<void> {
    return jsonFetch<void>("/ext/post-result", {
      method: "POST",
      body: JSON.stringify(result)
    });
  },

  // --- Aplicar (Pilar 3) ---
  getApplyQueue(): Promise<{ tasks: ApplyQueueTask[] }> {
    return jsonFetch<{ tasks: ApplyQueueTask[] }>("/ext/apply-queue");
  },

  reportApplied(report: AppliedReport): Promise<{ ok: boolean; job_status: string }> {
    return jsonFetch<{ ok: boolean; job_status: string }>("/ext/applied", {
      method: "POST",
      body: JSON.stringify(report)
    });
  },

  answerQuestion(payload: {
    job_id: number;
    question: string;
    options?: string[];
  }): Promise<{ answer: string; cached: boolean }> {
    return jsonFetch<{ answer: string; cached: boolean }>("/ext/answer-question", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  // Importa el PROPIO perfil de LinkedIn al onboarding (lectura de tu sesión).
  importLinkedinProfile(payload: {
    name?: string;
    headline?: string;
    summary?: string;
    profile_url?: string;
    skills?: string[];
    experience?: { role?: string; company?: string }[];
  }): Promise<{ ok: boolean }> {
    return jsonFetch<{ ok: boolean }>("/onboarding/linkedin/from-extension", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  }
};
