// Content script para la bandeja de mensajes: linkedin.com/messaging/*
//
// Cuando el usuario abre la bandeja:
//   1. Leemos hilos con mensajes no leídos del DOM.
//   2. Enviamos al backend (POST /ext/inbox-messages).
//   3. Recibimos hasta 3 respuestas sugeridas por hilo.
//   4. Mostramos un overlay con botones para insertar la respuesta elegida.

import { api } from "../lib/api";
import { humanType, sleep, waitFor } from "../lib/dom";
import { log } from "../lib/logger";
import { InboxMessage, InboxSuggestionsResponse } from "../lib/types";

log.info("messaging content script loaded");

const OVERLAY_ID = "jh-inbox-overlay";
let lastReportedHash = "";

window.addEventListener("load", () => {
  setTimeout(initMessaging, 3_500);
});

function initMessaging(): void {
  // Observamos el panel de hilos para detectar cambios
  const observer = new MutationObserver(() => {
    debouncedScan();
  });
  observer.observe(document.body, { childList: true, subtree: true });

  debouncedScan();
}

let scanTimer: number | undefined;
function debouncedScan(): void {
  if (scanTimer) window.clearTimeout(scanTimer);
  scanTimer = window.setTimeout(() => {
    scanInbox().catch((e) => log.error("scanInbox failed", e));
  }, 1500);
}

async function scanInbox(): Promise<void> {
  const messages = collectUnreadMessages();
  if (messages.length === 0) {
    removeOverlay();
    return;
  }

  // Evita reenviar si no cambió nada
  const hash = JSON.stringify(messages.map((m) => `${m.thread_id}:${m.preview}`));
  if (hash === lastReportedHash) return;
  lastReportedHash = hash;

  log.info(`scanInbox: ${messages.length} unread threads`);

  let suggestions: InboxSuggestionsResponse[] = [];
  try {
    suggestions = await api.reportInboxMessages({
      messages,
      collected_at: new Date().toISOString()
    });
  } catch (e) {
    log.warn("backend reply suggestion failed", (e as Error).message);
    return;
  }

  if (suggestions?.length) renderSuggestionsOverlay(suggestions);
}

function collectUnreadMessages(): InboxMessage[] {
  // LinkedIn marca hilos no leídos con `notification-badge` o estilo bold
  const threadNodes = Array.from(
    document.querySelectorAll<HTMLElement>(
      ".msg-conversations-container__convo-item, li.msg-conversation-listitem"
    )
  );

  const out: InboxMessage[] = [];
  for (const node of threadNodes) {
    const isUnread =
      node.classList.contains("msg-conversation-listitem--unread") ||
      !!node.querySelector(".notification-badge--show, .msg-conversation-card__pill") ||
      hasBoldName(node);

    if (!isUnread) continue;

    const name = node
      .querySelector(".msg-conversation-listitem__participant-names, .msg-conversation-card__participant-names")
      ?.textContent?.trim() ?? "Desconocido";
    const preview = node
      .querySelector(".msg-conversation-card__message-snippet, .msg-conversation-listitem__message-snippet")
      ?.textContent?.trim() ?? "";
    const threadId =
      node.getAttribute("data-conversation-id") ??
      node.querySelector("a[href*='/messaging/thread/']")?.getAttribute("href") ??
      crypto.randomUUID();

    out.push({
      thread_id: threadId,
      sender_name: name,
      preview,
      unread: true
    });
  }
  return out;
}

function hasBoldName(node: HTMLElement): boolean {
  const name = node.querySelector<HTMLElement>(
    ".msg-conversation-listitem__participant-names span"
  );
  if (!name) return false;
  const weight = window.getComputedStyle(name).fontWeight;
  return parseInt(weight, 10) >= 600;
}

// ---------------------------------------------------------------------------
// Overlay con sugerencias
// ---------------------------------------------------------------------------

function removeOverlay(): void {
  document.getElementById(OVERLAY_ID)?.remove();
}

function renderSuggestionsOverlay(items: InboxSuggestionsResponse[]): void {
  removeOverlay();

  const container = document.createElement("div");
  container.id = OVERLAY_ID;
  container.className = "jh-inbox-overlay";
  container.innerHTML = `
    <header class="jh-header">
      <span>JobHunter · respuestas sugeridas</span>
      <button class="jh-close" aria-label="Cerrar">x</button>
    </header>
    <div class="jh-body"></div>
  `;

  const body = container.querySelector<HTMLDivElement>(".jh-body")!;
  for (const item of items) {
    const block = document.createElement("section");
    block.className = "jh-thread";
    block.innerHTML = `<h4>Hilo ${escapeHtml(item.thread_id.slice(0, 12))}</h4>`;
    for (const suggestion of item.suggestions) {
      const btn = document.createElement("button");
      btn.className = "jh-suggestion";
      btn.textContent = suggestion;
      btn.addEventListener("click", () => insertSuggestion(suggestion));
      block.appendChild(btn);
    }
    body.appendChild(block);
  }

  container
    .querySelector(".jh-close")
    ?.addEventListener("click", () => removeOverlay());

  document.body.appendChild(container);
}

async function insertSuggestion(text: string): Promise<void> {
  try {
    const editor = (await waitFor(
      'div[role="textbox"][contenteditable="true"], .msg-form__contenteditable',
      5_000
    )) as HTMLElement;
    await humanType(editor, text);
  } catch (e) {
    log.error("insertSuggestion failed", e);
    // Fallback: copia al portapapeles
    await navigator.clipboard.writeText(text).catch(() => undefined);
  }
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!
  );
}
