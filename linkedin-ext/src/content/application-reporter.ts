/**
 * Reporter de aplicaciones (Pilar 3).
 *
 * Si la pagina actual corresponde a una oferta que el dashboard puso en la cola
 * de aplicar (GET /ext/apply-queue), muestra un panel flotante para marcarla
 * como enviada (POST /ext/applied) -> el backend mueve el pipeline a "applied".
 *
 * Complementa a application-autofill.ts (que rellena los campos). El usuario
 * sigue revisando y pulsando "Enviar" en la propia pagina del ATS.
 */
import { api, type ApplyQueueTask } from "../lib/api";

const PANEL_ID = "jobhunter-apply-panel";

function norm(s: string): string {
  return (s || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function matchTask(tasks: ApplyQueueTask[]): ApplyQueueTask | null {
  const href = location.href.toLowerCase();
  const host = location.hostname.toLowerCase();
  const title = norm(document.title);
  for (const t of tasks) {
    const url = (t.apply_url || "").toLowerCase();
    if (url && (href.includes(url) || url.includes(host))) return t;
    const company = norm(t.company);
    if (company.length >= 3 && title.includes(company)) return t;
  }
  return null;
}

function buildPanel(task: ApplyQueueTask): void {
  if (document.getElementById(PANEL_ID)) return;

  const panel = document.createElement("div");
  panel.id = PANEL_ID;
  panel.style.cssText = [
    "position:fixed", "bottom:20px", "right:20px", "z-index:2147483647",
    "background:#0b0f17", "color:#e6edf3", "border:1px solid #2b3648",
    "border-radius:12px", "padding:14px 16px", "width:280px",
    "font:13px/1.4 system-ui,sans-serif", "box-shadow:0 10px 40px rgba(0,0,0,.5)"
  ].join(";");

  const title = document.createElement("div");
  title.textContent = "JobHunter · aplicar";
  title.style.cssText = "font-weight:600;margin-bottom:4px;color:#39d0d8";

  const company = document.createElement("div");
  company.textContent = `${task.title} · ${task.company}`;
  company.style.cssText = "color:#9aa7b8;margin-bottom:10px;font-size:12px";

  const cvHint = document.createElement("div");
  if (task.materials?.cv_path) {
    cvHint.textContent = "Adjunta tu CV preparado (la extensión no puede subir archivos por ti).";
    cvHint.style.cssText = "color:#d8a657;margin-bottom:10px;font-size:11px";
  }

  const btn = document.createElement("button");
  btn.textContent = "✅ Marcar como enviada";
  btn.style.cssText = [
    "width:100%", "padding:8px", "border-radius:8px", "cursor:pointer",
    "background:#1f6feb22", "color:#58a6ff", "border:1px solid #1f6feb55", "font-weight:600"
  ].join(";");
  btn.onclick = async () => {
    btn.disabled = true;
    btn.textContent = "Enviando…";
    try {
      const r = await api.reportApplied({
        job_id: task.job_id,
        platform: task.platform,
        apply_url: location.href,
        status: "submitted",
        queue_id: task.queue_id
      });
      btn.textContent = `✓ Pipeline: ${r.job_status}`;
      btn.style.background = "#23863622";
      btn.style.color = "#3fb950";
      setTimeout(() => panel.remove(), 2500);
    } catch {
      btn.disabled = false;
      btn.textContent = "Error, reintentar";
    }
  };

  const close = document.createElement("button");
  close.textContent = "×";
  close.style.cssText = "position:absolute;top:8px;right:10px;background:none;border:none;color:#6b7688;cursor:pointer;font-size:16px";
  close.onclick = () => panel.remove();

  panel.append(close, title, company, cvHint, btn);
  document.body.appendChild(panel);
}

async function init(): Promise<void> {
  try {
    const { tasks } = await api.getApplyQueue();
    if (!tasks?.length) return;
    const match = matchTask(tasks);
    if (match) buildPanel(match);
  } catch {
    // backend offline o sin cola: no molestar.
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => void init());
} else {
  void init();
}
