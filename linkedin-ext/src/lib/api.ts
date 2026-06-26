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

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const base = await backend();
  const url = `${base}${path.startsWith("/") ? path : "/" + path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${res.statusText} :: ${body}`);
  }
  // Algunos endpoints pueden devolver 204
  if (res.status === 204) return undefined as unknown as T;
  return (await res.json()) as T;
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
  }
};
