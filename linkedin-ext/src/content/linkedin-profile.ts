// Content script para páginas de perfil: https://www.linkedin.com/in/*
// Ejecuta el flujo "Conectar + nota personalizada" cuando el background lo pide.

import {
  findByText,
  humanClick,
  humanType,
  sleep,
  waitFor,
  waitForAny,
  waitForPageReady,
  waitForText
} from "../lib/dom";
import { log } from "../lib/logger";
import { ConnectPersonTask, RuntimeMessage, RuntimeResponse } from "../lib/types";

log.info("profile content script loaded");

chrome.runtime.onMessage.addListener((msg: RuntimeMessage, _sender, sendResponse) => {
  if (msg.type === "CONNECT_WITH_NOTE") {
    runConnectFlow(msg.task)
      .then((res) => sendResponse(res))
      .catch((e) => sendResponse({ success: false, error: (e as Error).message } satisfies RuntimeResponse));
    return true; // async
  }
  return false;
});

async function runConnectFlow(task: ConnectPersonTask): Promise<RuntimeResponse> {
  try {
    log.info("runConnectFlow", task.profile_url);
    await waitForPageReady();

    // 1. Botón "Conectar" / "Connect"
    const connectBtn = await findConnectButton();
    await humanClick(connectBtn);

    // 2. Modal con "Añadir nota" / "Add a note"
    const addNoteBtn = await waitForText(
      ["añadir nota", "add a note", "agregar una nota"],
      8_000
    );
    await humanClick(addNoteBtn);

    // 3. Textarea de la nota
    const textarea = (await waitForAny(
      [
        'textarea[name="message"]',
        "#custom-message",
        'textarea[id*="custom-message"]'
      ],
      8_000
    )) as HTMLTextAreaElement;

    await humanType(textarea, task.message);
    await sleep(400);

    // 4. Botón "Enviar invitación" / "Send" / "Send invitation"
    const sendBtn = await waitForText(
      ["enviar invitación", "enviar invitacion", "send invitation", "enviar", "send"],
      8_000
    );
    await humanClick(sendBtn);

    // Verificación opcional: el modal se cierra o aparece toast
    await sleep(1500);

    return { success: true };
  } catch (e) {
    log.error("connect flow error", e);
    return { success: false, error: (e as Error).message };
  }
}

async function findConnectButton(): Promise<HTMLElement> {
  // Caso 1: botón visible directo
  const direct = findVisibleButton(["invit", "connect", "conect"]);
  if (direct) return direct;

  // Caso 2: dentro del menú "Más" / "More"
  const moreBtn = findVisibleButton(["más", "mas", "more"]);
  if (moreBtn) {
    await humanClick(moreBtn);
    await sleep(500);
    const fromMenu = findByText(["connect", "conectar"]);
    if (fromMenu) return fromMenu;
  }

  // Caso 3: a veces existe como rol "menuitem"
  const menuItems = Array.from(
    document.querySelectorAll<HTMLElement>('[role="menuitem"]')
  );
  const item = menuItems.find((m) =>
    /connect|conectar/i.test(m.textContent ?? "")
  );
  if (item) return item;

  throw new Error("No se encontró el botón Conectar en este perfil");
}

function findVisibleButton(keywords: string[]): HTMLElement | null {
  const all = Array.from(document.querySelectorAll<HTMLElement>("button"));
  for (const b of all) {
    if (!isVisible(b)) continue;
    const aria = (b.getAttribute("aria-label") ?? "").toLowerCase();
    const text = (b.textContent ?? "").trim().toLowerCase();
    if (keywords.some((k) => aria.includes(k) || text.includes(k))) {
      return b;
    }
  }
  return null;
}

function isVisible(el: HTMLElement): boolean {
  if (!el.isConnected) return false;
  const rect = el.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return false;
  const style = window.getComputedStyle(el);
  return style.visibility !== "hidden" && style.display !== "none";
}
