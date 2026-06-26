// Content script para el feed: https://www.linkedin.com/feed/*
// Maneja dos funcionalidades:
//   1. Programar una publicación (cuando background envía SCHEDULE_POST).
//   2. Sugerir comentarios sutiles al lado de posts relevantes (pasivo).

import {
  humanClick,
  humanType,
  sleep,
  waitFor,
  waitForAny,
  waitForPageReady,
  waitForText
} from "../lib/dom";
import { log } from "../lib/logger";
import {
  RuntimeMessage,
  RuntimeResponse,
  SchedulePostTask
} from "../lib/types";

log.info("feed content script loaded");

chrome.runtime.onMessage.addListener(
  (msg: RuntimeMessage | { type: "DEBUG_SCAN_FEED" }, _sender, sendResponse) => {
    if (msg.type === "SCHEDULE_POST") {
      runSchedulePostFlow(msg.task)
        .then((res) => sendResponse(res))
        .catch((e) => sendResponse({ success: false, error: (e as Error).message }));
      return true;
    }
    if (msg.type === "SUGGEST_COMMENTS") {
      initSuggestionsOverlay();
      sendResponse({ success: true } satisfies RuntimeResponse);
      return false;
    }
    if (msg.type === "DEBUG_SCAN_FEED") {
      debugScanNow()
        .then((res) => sendResponse(res))
        .catch((e) =>
          sendResponse({ ok: false, error: (e as Error).message })
        );
      return true;
    }
    return false;
  }
);

function findAllPostContainers(): HTMLElement[] {
  const containers = new Set<HTMLElement>();

  // Strategy 1: anything with urn:li:activity in known attributes
  const attrSelectors = [
    '[data-id*="urn:li:activity"]',
    '[data-urn*="urn:li:activity"]',
    '[id*="urn:li:activity"]',
    '[data-id*="urn:li:fsd_update"]',
    '[data-urn*="urn:li:fsd_update"]',
    '[data-finite-scroll-hotkey-item]',
  ];
  for (const sel of attrSelectors) {
    document.querySelectorAll<HTMLElement>(sel).forEach((el) => containers.add(el));
  }

  // Strategy 2: legacy class names (kept for backwards compat)
  const classSelectors = [
    ".feed-shared-update-v2",
    ".update-components-update-v2",
    ".fie-impression-container",
    ".scaffold-finite-scroll__content > div",
  ];
  for (const sel of classSelectors) {
    document.querySelectorAll<HTMLElement>(sel).forEach((el) => containers.add(el));
  }

  // Strategy 3: scan all attributes for "urn:li:activity"
  //   (covers cases where LinkedIn renames data-* attrs)
  document.querySelectorAll<HTMLElement>("[data-id], [data-urn], article, div[role='article']").forEach(
    (el) => {
      const allAttrs = Array.from(el.attributes)
        .map((a) => a.value)
        .join(" ");
      if (allAttrs.includes("urn:li:activity")) containers.add(el);
    }
  );

  // Strategy 4: anchors to /feed/update/urn:li:activity — climb to nearest article/section
  document
    .querySelectorAll<HTMLAnchorElement>('a[href*="urn:li:activity"]')
    .forEach((a) => {
      const ancestor =
        (a.closest("article") as HTMLElement | null) ??
        (a.closest('div[role="article"]') as HTMLElement | null) ??
        (a.closest(".feed-shared-update-v2") as HTMLElement | null) ??
        (a.closest("section") as HTMLElement | null);
      if (ancestor) containers.add(ancestor);
    });

  return Array.from(containers);
}

async function debugScanNow(): Promise<{
  ok: boolean;
  url: string;
  cards: number;
  extracted: number;
  sent: number;
  backendError?: string;
  sampleAuthor?: string;
  hints: string;
}> {
  const cards = findAllPostContainers();
  const extracted: CapturedPost[] = [];
  let rejectedReasons = {
    noUrn: 0,
    noAuthor: 0,
    shortContent: 0,
  };
  for (const c of cards) {
    const p = extractPostFromCard(c);
    if (p) {
      extracted.push(p);
    } else {
      if (!findURN(c)) rejectedReasons.noUrn += 1;
      else {
        const txt = (c.innerText ?? "").length;
        if (txt < 40) rejectedReasons.shortContent += 1;
        else rejectedReasons.noAuthor += 1;
      }
    }
  }
  log.info(`[debug-scan] cards=${cards.length} extracted=${extracted.length}`);

  let sent = 0;
  let backendError: string | undefined;
  if (extracted.length > 0) {
    try {
      const resp = await chrome.runtime.sendMessage({
        type: "SEND_FEED_POSTS",
        posts: extracted,
      });
      if (resp?.success) {
        sent = extracted.length;
      } else {
        backendError = resp?.error ?? "no response";
      }
    } catch (e) {
      backendError = (e as Error).message;
    }
  }

  const totalAnyActivity = document.querySelectorAll(
    '[data-id*="urn:li"], [data-urn*="urn:li"], a[href*="urn:li:activity"]'
  ).length;

  // Deep diagnostics — find out if LinkedIn is hiding posts in shadow DOM,
  // iframes, or just not serving them
  const html = document.documentElement.outerHTML;
  const stringHits = (html.match(/urn:li:activity/g) || []).length;
  const articleCount = document.querySelectorAll("article").length;
  const iframeCount = document.querySelectorAll("iframe").length;
  const mainEl = document.querySelector("main");
  const mainChildren = mainEl ? mainEl.querySelectorAll("*").length : 0;
  const feedContainer = document.querySelector(
    'main, [role="main"], .scaffold-finite-scroll, .feed-container'
  );
  const feedTextLen = feedContainer
    ? (feedContainer as HTMLElement).innerText.length
    : 0;

  // Look for shadow roots
  let shadowRoots = 0;
  document.querySelectorAll("*").forEach((el) => {
    if ((el as Element & { shadowRoot?: ShadowRoot }).shadowRoot) shadowRoots += 1;
  });

  const hints =
    `URL: ${location.pathname}\n` +
    `Doc lang: ${document.documentElement.lang || "?"}\n` +
    `Elementos con urn:li (queries): ${totalAnyActivity}\n` +
    `"urn:li:activity" en HTML crudo: ${stringHits}\n` +
    `<article> count: ${articleCount}\n` +
    `<iframe> count: ${iframeCount}\n` +
    `Shadow roots abiertos: ${shadowRoots}\n` +
    `Hijos en <main>: ${mainChildren}\n` +
    `Texto en feed container: ${feedTextLen} chars\n` +
    (cards.length === 0
      ? stringHits > 0
        ? "→ HAY urn:li en HTML pero los queries no lo cogen. Probable shadow DOM o iframe.\n"
        : feedTextLen < 500
          ? "→ El feed está vacío o no cargó. Adguard u otro bloqueador puede estar tumbando peticiones.\n"
          : "→ Hay contenido pero NO urn:li. LinkedIn rota IDs.\n"
      : `Rechazadas: ${rejectedReasons.noUrn} sin URN, ${rejectedReasons.noAuthor} sin autor, ${rejectedReasons.shortContent} contenido corto\n`);

  return {
    ok: true,
    url: location.href,
    cards: cards.length,
    extracted: extracted.length,
    sent,
    backendError,
    sampleAuthor: extracted[0]?.author_name,
    hints,
  };
}

// Inicializa overlay de sugerencias y feed scraper de forma pasiva.
// Arranca PRONTO (1.5s) — antes esperaba 4s y muchos usuarios scroll antes.
setTimeout(initSuggestionsOverlay, 1_500);
window.addEventListener("load", () => {
  setTimeout(initSuggestionsOverlay, 1_500);
});

// ---------------------------------------------------------------------------
// Schedule post
// ---------------------------------------------------------------------------

async function runSchedulePostFlow(
  task: SchedulePostTask
): Promise<RuntimeResponse> {
  try {
    log.info("schedule_post", task.post_id, task.scheduled_at);
    await waitForPageReady();

    // 1. Abrir el editor: botón "Empezar una publicación" / "Start a post"
    const startBtn = await waitForText(
      [
        "empezar una publicación",
        "empezar una publicacion",
        "start a post",
        "crear una publicación",
        "crear una publicacion"
      ],
      10_000
    );
    await humanClick(startBtn);

    // 2. Esperar al editor (contenteditable) en el modal
    const editor = (await waitForAny(
      [
        'div[role="textbox"][contenteditable="true"]',
        '.ql-editor[contenteditable="true"]'
      ],
      10_000
    )) as HTMLElement;

    // 3. Pegar contenido
    let content = task.content;
    if (task.hashtags?.length) {
      content += "\n\n" + task.hashtags.map((h) => (h.startsWith("#") ? h : "#" + h)).join(" ");
    }
    await humanType(editor, content);
    await sleep(600);

    // 4. Imagen (opcional) — TODO: requiere descargar y subir via input[type=file]
    if (task.image_url) {
      log.warn("image_url presente pero adjuntar imágenes aún no está implementado");
    }

    // 5. Click ícono "reloj" (programar)
    const scheduleBtn = await findScheduleButton();
    await humanClick(scheduleBtn);

    // 6. Setear fecha + hora en el diálogo
    await setScheduleDateTime(task.scheduled_at);

    // 7. Confirmar "Siguiente" / "Next"
    const nextBtn = await waitForText(["siguiente", "next"], 6_000);
    await humanClick(nextBtn);

    // 8. Click "Programar" / "Schedule"
    const finalBtn = await waitForText(["programar", "schedule"], 6_000);
    await humanClick(finalBtn);

    return { success: true };
  } catch (e) {
    log.error("schedule_post error", e);
    return { success: false, error: (e as Error).message };
  }
}

async function findScheduleButton(): Promise<HTMLElement> {
  // El botón "reloj" para programar tiene aria-label en ES/EN
  const buttons = Array.from(document.querySelectorAll<HTMLElement>("button"));
  const found = buttons.find((b) => {
    const aria = (b.getAttribute("aria-label") ?? "").toLowerCase();
    return (
      aria.includes("programar") ||
      aria.includes("schedule") ||
      aria.includes("clock")
    );
  });
  if (!found) throw new Error("No se encontró botón de programar publicación");
  return found;
}

async function setScheduleDateTime(isoDate: string): Promise<void> {
  const d = new Date(isoDate);
  // Formato esperado en LinkedIn: dd/mm/yyyy ES, mm/dd/yyyy EN
  // Detectamos el lang del documento para decidir formato
  const lang = document.documentElement.lang?.toLowerCase() ?? "en";
  const isES = lang.startsWith("es");

  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = String(d.getFullYear());
  const dateStr = isES ? `${dd}/${mm}/${yyyy}` : `${mm}/${dd}/${yyyy}`;
  const hh = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");

  // Input fecha
  const dateInput = (await waitForAny(
    ['input[name="date"]', 'input[placeholder*="/"]', 'input[type="text"][aria-label*="fecha" i]'],
    8_000
  )) as HTMLInputElement;
  await humanType(dateInput, dateStr);

  // Input hora — LinkedIn suele tener un select. Intentamos ambos.
  const timeInputs = Array.from(
    document.querySelectorAll<HTMLInputElement | HTMLSelectElement>(
      'input[name="time"], select[name="time"], input[aria-label*="hora" i], input[aria-label*="time" i]'
    )
  );
  if (timeInputs.length > 0) {
    const t = timeInputs[0];
    if (t.tagName === "SELECT") {
      const select = t as HTMLSelectElement;
      const target = `${hh}:${min}`;
      const option = Array.from(select.options).find((o) =>
        o.text.includes(target)
      );
      if (option) {
        select.value = option.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
    } else {
      await humanType(t as HTMLInputElement, `${hh}:${min}`);
    }
  }
  await sleep(500);
}

// ---------------------------------------------------------------------------
// Suggest comments overlay (pasivo)
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Feed scraping: captura posts visibles del feed y los envía al backend para
// que Claude genere comentarios sugeridos.
// ---------------------------------------------------------------------------

interface CapturedPost {
  post_url: string;
  author_name?: string;
  author_headline?: string;
  author_url?: string;
  content_excerpt?: string;
  language?: string;
}

const sentUrns = new Set<string>();

function findURN(card: HTMLElement): string | null {
  const candidates: (string | null)[] = [
    card.getAttribute("data-id"),
    card.getAttribute("data-urn"),
    card.querySelector("[data-urn]")?.getAttribute("data-urn") ?? null,
    card.querySelector("[data-id]")?.getAttribute("data-id") ?? null,
  ];
  for (const s of candidates) {
    if (!s) continue;
    const m = s.match(/urn:li:activity:(\d+)/);
    if (m) return m[1];
  }
  // Fallback: a link to /feed/update/urn:li:activity:...
  const link = card.querySelector<HTMLAnchorElement>(
    'a[href*="urn:li:activity"]',
  );
  if (link) {
    const m = link.href.match(/urn:li:activity:(\d+)/);
    if (m) return m[1];
  }
  return null;
}

function pickText(card: HTMLElement, selectors: string[]): string {
  for (const sel of selectors) {
    const el = card.querySelector<HTMLElement>(sel);
    if (el) {
      const t = (el.innerText ?? el.textContent ?? "").trim();
      if (t) return t;
    }
  }
  return "";
}

function extractPostFromCard(card: HTMLElement): CapturedPost | null {
  const activityId = findURN(card);
  if (!activityId) return null;
  const url = `https://www.linkedin.com/feed/update/urn:li:activity:${activityId}/`;
  if (sentUrns.has(url)) return null;

  const authorName = pickText(card, [
    ".update-components-actor__title",
    ".feed-shared-actor__name",
    ".update-components-actor__name",
    'span[aria-hidden="true"]',
    "a strong",
  ])
    .split("\n")[0]
    .trim()
    .replace(/\s*•.*$/, "")
    .slice(0, 120);

  const authorHeadline = pickText(card, [
    ".update-components-actor__description",
    ".feed-shared-actor__description",
    ".update-components-actor__sub-description",
  ]).slice(0, 200);

  const authorAnchor = card.querySelector<HTMLAnchorElement>(
    'a[href*="/in/"], a[href*="/company/"], a[href*="/school/"]',
  );

  const content = pickText(card, [
    ".update-components-text",
    ".feed-shared-update-v2__description",
    ".feed-shared-inline-show-more-text",
    'span[dir="ltr"]',
  ]);

  if (!authorName || content.length < 40) {
    return null;
  }

  const lang = document.documentElement.lang?.split("-")[0] ?? "en";
  return {
    post_url: url,
    author_name: authorName,
    author_headline: authorHeadline || undefined,
    author_url: authorAnchor?.href,
    content_excerpt: content.slice(0, 1500),
    language: lang,
  };
}

async function flushBatch(batch: CapturedPost[]): Promise<void> {
  if (batch.length === 0) return;
  if (!chrome.runtime?.id) {
    log.warn("feed flush skipped: extension context invalidated, reload page");
    return;
  }
  try {
    const resp = await chrome.runtime.sendMessage({
      type: "SEND_FEED_POSTS",
      posts: batch,
    });
    if (resp?.success) {
      for (const p of batch) sentUrns.add(p.post_url);
      log.info(`feed: sent ${batch.length} posts to backend`);
    } else {
      log.warn("feed flush refused", resp?.error ?? "no response");
    }
  } catch (e) {
    const msg = (e as Error).message;
    if (/Extension context invalidated/i.test(msg)) {
      log.warn(
        "feed flush failed: extension reloaded — please F5 this tab to reactivate JobHunter"
      );
    } else {
      log.warn("feed flush failed", msg);
    }
  }
}

function initFeedScraper(): void {
  log.info("[feed-scraper] init on", location.href);
  let pending: CapturedPost[] = [];
  let timer: number | null = null;
  let scanCount = 0;
  let lastReport = 0;

  const flush = async () => {
    const batch = pending;
    pending = [];
    timer = null;
    if (batch.length === 0) return;
    log.info(`[feed-scraper] flushing ${batch.length} posts`);
    await flushBatch(batch);
  };

  const scheduleFlush = () => {
    if (timer != null) return;
    timer = window.setTimeout(() => {
      flush().catch(() => {});
    }, 1500);
  };

  const scan = () => {
    scanCount += 1;
    const cards = Array.from(
      document.querySelectorAll<HTMLElement>(
        '[data-id^="urn:li:activity"], [data-urn^="urn:li:activity"], .feed-shared-update-v2, [data-id*="urn:li:fsd_update"]',
      ),
    );

    // Periodic summary so the user can see if the scraper is even running
    const now = Date.now();
    if (now - lastReport > 5000) {
      log.info(
        `[feed-scraper] scan #${scanCount}: found ${cards.length} card candidates on page`,
      );
      lastReport = now;
    }

    let added = 0;
    let rejected = 0;
    for (const c of cards) {
      const post = extractPostFromCard(c);
      if (post && !pending.some((p) => p.post_url === post.post_url)) {
        pending.push(post);
        added += 1;
      } else if (!post) {
        rejected += 1;
      }
    }
    if (added > 0) {
      log.info(
        `[feed-scraper] +${added} new posts queued (${rejected} rejected, ${pending.length} total pending)`,
      );
    }
    if (pending.length >= 5) {
      flush().catch(() => {});
    } else if (pending.length > 0) {
      scheduleFlush();
    }
  };

  scan();
  const observer = new MutationObserver(() => scan());
  observer.observe(document.body, { childList: true, subtree: true });
}

function initSuggestionsOverlay(): void {
  // Replaces the old no-op: now we actively scrape feed posts and send them
  // to the backend so /comments/suggestions has real data.
  initFeedScraper();
}
