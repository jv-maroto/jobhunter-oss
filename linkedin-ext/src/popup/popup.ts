// Popup: muestra estado + accesos directos al dashboard.

import { api } from "../lib/api";
import { getSettings, setSettings } from "../lib/storage";
import { ExtTasksResponse } from "../lib/types";

const $ = <T extends HTMLElement = HTMLElement>(id: string): T =>
  document.getElementById(id) as T;

async function init(): Promise<void> {
  const settings = await getSettings();
  $("backend-url").textContent = settings.backend_url;
  ($("auto-toggle") as HTMLInputElement).checked = settings.auto_execute;

  $("auto-toggle").addEventListener("change", async (e) => {
    const checked = (e.target as HTMLInputElement).checked;
    await setSettings({ auto_execute: checked });
  });

  $("dashboard-btn").addEventListener("click", async () => {
    const dashboardUrl =
      settings.dashboard_url ??
      settings.backend_url.replace(/:8000.*$/, ":3000") ??
      "http://localhost:3000";
    try {
      await chrome.tabs.create({ url: dashboardUrl, active: true });
    } catch (err) {
      console.error("dashboard-btn open failed", err, "url=", dashboardUrl);
      try {
        window.open(dashboardUrl, "_blank");
      } catch (err2) {
        console.error("window.open fallback failed", err2);
        const msg = err instanceof Error ? err.message : String(err);
        $("status-text").textContent = `Error abriendo dashboard: ${msg}`;
      }
    }
  });

  $("options-btn").addEventListener("click", () => {
    chrome.runtime.openOptionsPage();
  });

  $("poll-btn").addEventListener("click", async () => {
    $("poll-btn").textContent = "Sincronizando...";
    try {
      await chrome.runtime.sendMessage({ type: "FORCE_POLL" });
    } finally {
      $("poll-btn").textContent = "Forzar sincronización";
      await refresh();
    }
  });

  $("scan-btn").addEventListener("click", async () => {
    const out = $("diag-output");
    const btn = $("scan-btn") as HTMLButtonElement;
    btn.disabled = true;
    btn.textContent = "Capturando…";
    out.textContent = "Buscando pestaña activa…";
    try {
      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
      });
      if (!tab?.id) {
        out.textContent = "No hay pestaña activa.";
        return;
      }
      if (!/linkedin\.com\/(feed|in|company|jobs|search)/.test(tab.url ?? "")) {
        out.textContent = `Esta pestaña no es de LinkedIn:\n${tab.url ?? ""}\nVe a linkedin.com/feed/ y vuelve a pulsar.`;
        return;
      }
      out.textContent = `Pestaña: ${tab.url}\nLanzando captura…`;
      const result = await chrome.tabs
        .sendMessage(tab.id, { type: "DEBUG_SCAN_FEED" })
        .catch((e) => ({
          ok: false,
          error: (e as Error).message,
        }));
      if (result?.ok) {
        out.textContent =
          `Cards encontradas: ${result.cards}\n` +
          `Posts extraídos: ${result.extracted}\n` +
          `Enviados al backend: ${result.sent}\n` +
          (result.backendError ? `Error backend: ${result.backendError}\n` : "") +
          (result.hints ? `\n${result.hints}` : "");
      } else {
        out.textContent =
          "Content script no respondió. Posibles causas:\n" +
          "- La extensión no está cargada en esta pestaña\n" +
          "- LinkedIn cambió selectores\n" +
          "- Error: " +
          (result?.error ?? "unknown");
      }
    } catch (e) {
      out.textContent = `Error: ${(e as Error).message}`;
    } finally {
      btn.disabled = false;
      btn.textContent = "Capturar posts de esta página";
    }
  });

  await refresh();
}

async function refresh(): Promise<void> {
  const dot = $("status-dot");
  const statusText = $("status-text");

  try {
    const ok = await api.health();
    if (ok) {
      dot.classList.add("ok");
      dot.classList.remove("bad");
      statusText.textContent = "Conectado al dashboard";
    } else {
      throw new Error("backend no responde");
    }
  } catch (e) {
    dot.classList.add("bad");
    dot.classList.remove("ok");
    statusText.textContent = "Sin conexión con el dashboard";
    $("num-connect").textContent = "--";
    $("num-posts").textContent = "--";
    $("num-msgs").textContent = "--";
    return;
  }

  // Cargar resumen
  try {
    const tasks: ExtTasksResponse = await api.getTasks();
    const counts = tasks.tasks.reduce(
      (acc, t) => {
        if (t.type === "connect_person") acc.connect += 1;
        else if (t.type === "schedule_post") acc.posts += 1;
        else if (t.type === "read_inbox") acc.msgs += 1;
        return acc;
      },
      { connect: 0, posts: 0, msgs: 0 }
    );
    $("num-connect").textContent = String(counts.connect);
    $("num-posts").textContent = String(counts.posts);
    $("num-msgs").textContent = String(counts.msgs);
    $("last-poll").textContent = new Date().toLocaleTimeString();
  } catch {
    $("num-connect").textContent = "?";
    $("num-posts").textContent = "?";
    $("num-msgs").textContent = "?";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  init().catch((e) => console.error("popup init", e));
});
