// Service worker que orquesta la extensión.
//
// Responsabilidades:
//   - Hacer polling periódico al backend para obtener tareas pendientes.
//   - Abrir/recuperar pestañas LinkedIn según la tarea.
//   - Enviar mensajes al content script y reportar el resultado al backend.

import { api } from "../lib/api";
import { log } from "../lib/logger";
import { getSettings } from "../lib/storage";
import {
  ConnectPersonTask,
  ExtTask,
  RuntimeMessage,
  RuntimeResponse,
  SchedulePostTask
} from "../lib/types";

const POLL_ALARM = "jobhunter-poll";
const PROCESSED_TASKS_KEY = "processed_task_ids";
const MAX_TASKS_PER_TICK = 1; // Conservador: una acción "humana" por tick

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

chrome.runtime.onInstalled.addListener(async () => {
  log.info("onInstalled");
  await scheduleAlarm();
});

chrome.runtime.onStartup.addListener(async () => {
  log.info("onStartup");
  await scheduleAlarm();
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === POLL_ALARM) {
    await pollTick().catch((e) => log.error("pollTick error", e));
  }
});

chrome.runtime.onMessage.addListener(
  (msg: RuntimeMessage, _sender, sendResponse) => {
    (async () => {
      try {
        if (msg.type === "PING_STATUS") {
          const settings = await getSettings();
          const ok = await api.health();
          sendResponse({
            success: true,
            data: { backend_ok: ok, settings }
          } satisfies RuntimeResponse);
          return;
        }
        if (msg.type === "FORCE_POLL") {
          await pollTick();
          sendResponse({ success: true } satisfies RuntimeResponse);
          return;
        }
        if (msg.type === "GET_PROFILE") {
          const settings = await getSettings();
          const base = settings.backend_url.replace(/\/+$/, "");
          try {
            const res = await fetch(`${base}/ext/profile`, {
              headers: { Accept: "application/json" }
            });
            if (!res.ok) {
              sendResponse({
                success: false,
                error: `HTTP ${res.status}`
              } satisfies RuntimeResponse);
              return;
            }
            const data = await res.json();
            sendResponse({
              success: true,
              data
            } satisfies RuntimeResponse);
          } catch (e) {
            sendResponse({
              success: false,
              error: (e as Error).message
            } satisfies RuntimeResponse);
          }
          return;
        }
        if (msg.type === "GENERATE_COMMENT_FOR_POST") {
          const settings = await getSettings();
          const base = settings.backend_url.replace(/\/+$/, "");
          try {
            const res = await fetch(`${base}/comments/manual-post`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(msg.payload ?? {})
            });
            if (!res.ok) {
              const txt = await res.text().catch(() => "");
              sendResponse({
                success: false,
                error: `HTTP ${res.status} ${txt.slice(0, 120)}`
              } satisfies RuntimeResponse);
              return;
            }
            const data = await res.json();
            sendResponse({ success: true, data } satisfies RuntimeResponse);
          } catch (e) {
            sendResponse({
              success: false,
              error: (e as Error).message
            } satisfies RuntimeResponse);
          }
          return;
        }
        if (msg.type === "SEND_FEED_POSTS") {
          const settings = await getSettings();
          const base = settings.backend_url.replace(/\/+$/, "");
          const payload = { posts: msg.posts ?? [] };
          try {
            const res = await fetch(`${base}/comments/feed-posts`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload)
            });
            if (!res.ok) {
              sendResponse({
                success: false,
                error: `HTTP ${res.status}`
              } satisfies RuntimeResponse);
              return;
            }
            const data = await res.json();
            sendResponse({ success: true, data } satisfies RuntimeResponse);
          } catch (e) {
            sendResponse({
              success: false,
              error: (e as Error).message
            } satisfies RuntimeResponse);
          }
          return;
        }
        sendResponse({ success: false, error: "Unknown message" });
      } catch (e) {
        sendResponse({
          success: false,
          error: (e as Error).message
        } satisfies RuntimeResponse);
      }
    })();
    return true; // async
  }
);

// ---------------------------------------------------------------------------
// Polling
// ---------------------------------------------------------------------------

async function scheduleAlarm(): Promise<void> {
  const settings = await getSettings();
  // Mínimo de Chrome es 1 minuto para alarms periódicos; convertimos seconds.
  const periodMinutes = Math.max(0.5, settings.poll_interval_seconds / 60);
  await chrome.alarms.clear(POLL_ALARM);
  await chrome.alarms.create(POLL_ALARM, { periodInMinutes: periodMinutes });
  log.info(`alarm scheduled every ${periodMinutes.toFixed(2)} min`);
}

// Serializa los ticks dentro del mismo service worker. Sin esto, la alarma y
// un FORCE_POLL del popup pueden solaparse: ambos leen el mismo set "procesado"
// antes de que el otro lo guarde y ejecutan la misma tarea dos veces (p.ej.
// enviar la misma nota de conexión / publicar el mismo post por duplicado).
let pollLock: Promise<void> = Promise.resolve();

function pollTick(): Promise<void> {
  const next = pollLock.then(pollTickInner, pollTickInner);
  // El lock nunca queda "rechazado" para no romper los ticks siguientes.
  pollLock = next.then(
    () => undefined,
    () => undefined,
  );
  return next;
}

async function pollTickInner(): Promise<void> {
  const settings = await getSettings();
  if (!settings.auto_execute) {
    log.debug("auto_execute=false, skip tick");
    return;
  }

  let resp;
  try {
    resp = await api.getTasks();
  } catch (e) {
    log.warn("getTasks failed", (e as Error).message);
    return;
  }

  if (!resp.tasks?.length) {
    log.debug("no tasks");
    return;
  }

  const processed = await getProcessedSet();
  const fresh = resp.tasks.filter((t) => !processed.has(t.id));
  const slice = fresh.slice(0, MAX_TASKS_PER_TICK);
  log.info(`tick: ${slice.length}/${fresh.length} fresh tasks`);

  for (const task of slice) {
    try {
      await executeTask(task);
    } catch (e) {
      log.error(`task ${task.id} failed`, (e as Error).message);
    } finally {
      processed.add(task.id);
    }
  }

  await saveProcessedSet(processed);
}

async function executeTask(task: ExtTask): Promise<void> {
  switch (task.type) {
    case "connect_person":
      return execConnect(task);
    case "schedule_post":
      return execSchedulePost(task);
    case "read_inbox":
      // Esto se ejecuta de forma pasiva cuando el usuario está en messaging.
      log.debug("read_inbox: nada que hacer activo, content script lo cubre");
      return;
    case "suggest_comments":
      log.debug("suggest_comments: feed content script lo cubre");
      return;
  }
}

// ---------------------------------------------------------------------------
// Connect person
// ---------------------------------------------------------------------------

async function execConnect(task: ConnectPersonTask): Promise<void> {
  log.info("execConnect", task.profile_url);
  const tab = await openOrReuseTab(task.profile_url);
  await waitTabComplete(tab.id!);

  const response = await sendToTab<RuntimeResponse>(tab.id!, {
    type: "CONNECT_WITH_NOTE",
    task
  });

  await api.reportConnectResult({
    task_id: task.id,
    person_id: task.person_id,
    success: response.success,
    error: response.error,
    executed_at: new Date().toISOString()
  });
}

// ---------------------------------------------------------------------------
// Schedule post
// ---------------------------------------------------------------------------

async function execSchedulePost(task: SchedulePostTask): Promise<void> {
  log.info("execSchedulePost", task.post_id);
  const tab = await openOrReuseTab("https://www.linkedin.com/feed/");
  await waitTabComplete(tab.id!);

  const response = await sendToTab<RuntimeResponse>(tab.id!, {
    type: "SCHEDULE_POST",
    task
  });

  log.info("schedule_post result", response);

  try {
    await api.reportPostResult({
      task_id: task.id,
      post_id: task.post_id,
      success: response.success,
      error: response.error,
      scheduled_at: task.scheduled_at
    });
  } catch (e) {
    log.warn("reportPostResult failed", (e as Error).message);
  }
}

// ---------------------------------------------------------------------------
// Helpers de pestañas
// ---------------------------------------------------------------------------

async function openOrReuseTab(url: string): Promise<chrome.tabs.Tab> {
  const [existing] = await chrome.tabs.query({ url: matchPattern(url) });
  if (existing?.id != null) {
    await chrome.tabs.update(existing.id, { active: true, url });
    return existing;
  }
  return chrome.tabs.create({ url, active: true });
}

function matchPattern(url: string): string {
  // Convierte una URL específica en un match-pattern amplio del mismo host
  try {
    const u = new URL(url);
    return `${u.protocol}//${u.host}/*`;
  } catch {
    return url;
  }
}

function waitTabComplete(tabId: number, timeout = 30_000): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      reject(new Error("Timeout esperando a que la pestaña cargue"));
    }, timeout);

    const listener = (
      changedId: number,
      info: chrome.tabs.TabChangeInfo
    ): void => {
      if (changedId === tabId && info.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        clearTimeout(timer);
        // Damos un margen para que el content script inicialice
        setTimeout(resolve, 1200);
      }
    };
    chrome.tabs.onUpdated.addListener(listener);

    // Comprueba estado inicial: si ya está complete, resolvemos ya
    chrome.tabs.get(tabId).then((t) => {
      if (t.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        clearTimeout(timer);
        setTimeout(resolve, 1200);
      }
    });
  });
}

async function sendToTab<T>(tabId: number, message: RuntimeMessage): Promise<T> {
  try {
    return (await chrome.tabs.sendMessage(tabId, message)) as T;
  } catch (e) {
    throw new Error(
      `No se pudo entregar mensaje al content script (tab ${tabId}): ${(e as Error).message}`
    );
  }
}

// ---------------------------------------------------------------------------
// Set persistido de task IDs ya procesadas
// ---------------------------------------------------------------------------

async function getProcessedSet(): Promise<Set<string>> {
  const raw = await chrome.storage.local.get(PROCESSED_TASKS_KEY);
  const list = (raw[PROCESSED_TASKS_KEY] as string[]) ?? [];
  // Recortamos para no crecer infinito
  return new Set(list.slice(-500));
}

async function saveProcessedSet(set: Set<string>): Promise<void> {
  await chrome.storage.local.set({
    [PROCESSED_TASKS_KEY]: Array.from(set).slice(-500)
  });
}

// Re-programar alarm si cambia el intervalo en settings
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.settings) {
    scheduleAlarm().catch((e) => log.error("re-schedule alarm", e));
  }
});
