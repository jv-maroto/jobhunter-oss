// Página de opciones: persiste settings en chrome.storage.local.

import { api } from "../lib/api";
import { getSettings, setSettings } from "../lib/storage";
import { SimSpeed } from "../lib/types";

const $ = <T extends HTMLElement = HTMLElement>(id: string): T =>
  document.getElementById(id) as T;

async function init(): Promise<void> {
  const s = await getSettings();
  ($("backend_url") as HTMLInputElement).value = s.backend_url;
  ($("sim_speed") as HTMLSelectElement).value = s.sim_speed;
  ($("poll_interval_seconds") as HTMLInputElement).value = String(s.poll_interval_seconds);
  ($("auto_execute") as HTMLInputElement).checked = s.auto_execute;

  $("save").addEventListener("click", save);
  $("test").addEventListener("click", test);
}

async function save(): Promise<void> {
  const backend_url = ($("backend_url") as HTMLInputElement).value.trim();
  const sim_speed = ($("sim_speed") as HTMLSelectElement).value as SimSpeed;
  const poll_interval_seconds = parseInt(
    ($("poll_interval_seconds") as HTMLInputElement).value,
    10
  );
  const auto_execute = ($("auto_execute") as HTMLInputElement).checked;

  if (!backend_url.startsWith("http")) {
    showStatus("URL inválida (debe empezar con http/https)", "err");
    return;
  }

  await setSettings({
    backend_url: backend_url.replace(/\/+$/, ""),
    sim_speed,
    poll_interval_seconds: Math.max(30, Math.min(3600, poll_interval_seconds || 30)),
    auto_execute
  });
  showStatus("Guardado", "ok");
}

async function test(): Promise<void> {
  showStatus("Probando conexión...", "ok");
  const ok = await api.health();
  if (ok) showStatus("Backend responde correctamente", "ok");
  else showStatus("No se pudo conectar con el backend", "err");
}

function showStatus(msg: string, kind: "ok" | "err"): void {
  const el = $("status");
  el.textContent = msg;
  el.className = `status ${kind}`;
}

document.addEventListener("DOMContentLoaded", () => {
  init().catch((e) => console.error("options init", e));
});
