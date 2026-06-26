// LinkedIn post-helper content script.
//
// Activates on ANY LinkedIn page. Shows a floating pill in the bottom-right
// that says "JobHunter · Sugerir comentario para este post". When clicked it:
//   1. Reads the main visible text on the page (the post content the user is
//      currently looking at).
//   2. Sends it to the background worker → backend POST /comments/manual-post
//      with author info if available.
//   3. Receives a suggested comment from Claude.
//   4. Renders an overlay with the suggestion + buttons "Copy" and "Regenerate".
//
// Works without scraping URNs or IDs — LinkedIn's anti-scraping changes don't
// hurt us because we only read the rendered TEXT the user sees.

import { log } from "../lib/logger";

const PILL_ID = "jobhunter-post-helper-pill";
const PANEL_ID = "jobhunter-post-helper-panel";

interface PostExtraction {
  url: string;
  author_name: string;
  author_headline: string;
  content: string;
  language: string;
}

function isLikelyPostPage(): boolean {
  // Heuristic: are we on a single-post URL, or any LinkedIn page that has
  // post-like content (we'll let the user decide on any LinkedIn page).
  return /linkedin\.com\//.test(location.href);
}

function pickLongestVisibleTextBlock(): HTMLElement | null {
  // Walk the DOM looking for the element with the longest visible innerText
  // that lives under <main>. Skip nav/aside/footer.
  const main =
    document.querySelector("main") ??
    document.querySelector('[role="main"]') ??
    document.body;
  let best: HTMLElement | null = null;
  let bestLen = 0;
  const walker = document.createTreeWalker(main, NodeFilter.SHOW_ELEMENT, {
    acceptNode(node) {
      const el = node as HTMLElement;
      const tag = el.tagName.toLowerCase();
      if (["nav", "aside", "footer", "header", "script", "style"].includes(tag)) {
        return NodeFilter.FILTER_REJECT;
      }
      if (el.getAttribute("aria-hidden") === "true") return NodeFilter.FILTER_SKIP;
      const rect = el.getBoundingClientRect();
      if (rect.width < 200 || rect.height < 50) return NodeFilter.FILTER_SKIP;
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  let node = walker.nextNode();
  while (node) {
    const el = node as HTMLElement;
    // Only consider blocks that don't have a meaningful child block (leaf-ish)
    const childBlocks = el.querySelectorAll("div, section, article, p");
    const childTextLen = Array.from(childBlocks).reduce(
      (acc, c) => acc + (c as HTMLElement).innerText.length,
      0,
    );
    const text = el.innerText ?? "";
    // If the element's own non-descendant text is significant
    const ownLen = text.length;
    // Prefer elements whose text is mostly their own (not summed from children)
    if (ownLen > bestLen && ownLen - childTextLen < ownLen * 0.4) {
      best = el;
      bestLen = ownLen;
    }
    if (ownLen > bestLen * 1.5) {
      best = el;
      bestLen = ownLen;
    }
    node = walker.nextNode();
  }
  return best;
}

function extractAuthorInfo(): {
  name: string;
  headline: string;
} {
  // Look for h1 / h2 / strong / a near the top of <main> that looks like a name
  const main =
    document.querySelector("main") ?? document.querySelector('[role="main"]');
  if (!main) return { name: "", headline: "" };

  const candidates = Array.from(
    main.querySelectorAll<HTMLElement>(
      "h1, h2, h3, strong, a[href*='/in/'], a[href*='/company/']",
    ),
  ).slice(0, 30);

  let name = "";
  let headline = "";
  for (const c of candidates) {
    const t = (c.innerText ?? c.textContent ?? "").trim();
    if (!t || t.length > 120) continue;
    // Names are usually 2-5 words, no punctuation other than - or .
    if (!name && /^[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑáéíóú]+(\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑáéíóú]+)+$/.test(t)) {
      name = t;
      // Headline often appears in the same area, after the name
      const next = c.nextElementSibling as HTMLElement | null;
      if (next) {
        const nt = (next.innerText ?? next.textContent ?? "").trim();
        if (nt && nt.length < 200) headline = nt;
      }
      break;
    }
  }
  return { name, headline };
}

function extractPost(): PostExtraction | null {
  const block = pickLongestVisibleTextBlock();
  const content = (block?.innerText ?? "").trim().slice(0, 2000);
  if (content.length < 50) {
    return null;
  }
  const { name, headline } = extractAuthorInfo();
  const lang = document.documentElement.lang?.split("-")[0] ?? "en";
  return {
    url: location.href,
    author_name: name || "Unknown",
    author_headline: headline,
    content,
    language: lang,
  };
}

// ---------------------------------------------------------------------------
// UI
// ---------------------------------------------------------------------------

function mountPill(onClick: () => void): void {
  if (document.getElementById(PILL_ID)) return;
  const pill = document.createElement("button");
  pill.id = PILL_ID;
  pill.type = "button";
  Object.assign(pill.style, {
    position: "fixed",
    right: "20px",
    bottom: "20px",
    zIndex: "2147483646",
    display: "inline-flex",
    alignItems: "center",
    gap: "8px",
    padding: "10px 14px",
    borderRadius: "999px",
    background: "rgba(11, 14, 22, 0.92)",
    color: "#fafafa",
    border: "1px solid rgba(34, 211, 238, 0.45)",
    boxShadow: "0 8px 32px -8px rgba(34, 211, 238, 0.6)",
    backdropFilter: "blur(10px)",
    fontFamily:
      'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    fontSize: "12px",
    fontWeight: "600",
    cursor: "pointer",
    letterSpacing: "0.02em",
  } as CSSStyleDeclaration);
  pill.innerHTML = `
    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#22d3ee;box-shadow:0 0 8px #22d3ee;"></span>
    JobHunter · Sugerir comentario
  `;
  pill.addEventListener("click", onClick);
  document.body.appendChild(pill);
}

function showPanel(state: {
  status: string;
  body?: string;
  comment?: string;
  onCopy?: () => void;
  onRegenerate?: () => void;
  onClose?: () => void;
}): void {
  let panel = document.getElementById(PANEL_ID);
  if (!panel) {
    panel = document.createElement("div");
    panel.id = PANEL_ID;
    Object.assign(panel.style, {
      position: "fixed",
      right: "20px",
      bottom: "76px",
      zIndex: "2147483646",
      width: "360px",
      maxHeight: "440px",
      padding: "14px 16px",
      borderRadius: "16px",
      background: "rgba(11, 14, 22, 0.96)",
      color: "#fafafa",
      border: "1px solid rgba(34, 211, 238, 0.35)",
      boxShadow: "0 16px 60px -8px rgba(0,0,0,0.6)",
      backdropFilter: "blur(12px)",
      fontFamily:
        'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      fontSize: "12px",
      lineHeight: "1.5",
      overflow: "hidden",
      display: "flex",
      flexDirection: "column",
      gap: "10px",
    } as CSSStyleDeclaration);
    document.body.appendChild(panel);
  }
  panel.innerHTML = "";

  const header = document.createElement("div");
  Object.assign(header.style, {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    fontSize: "10px",
    letterSpacing: "0.18em",
    textTransform: "uppercase",
    color: "rgba(34, 211, 238, 0.9)",
    fontWeight: "600",
  } as CSSStyleDeclaration);
  header.textContent = state.status;
  const closeBtn = document.createElement("button");
  closeBtn.textContent = "✕";
  Object.assign(closeBtn.style, {
    background: "transparent",
    border: "none",
    color: "#94a3b8",
    cursor: "pointer",
    fontSize: "16px",
    lineHeight: "1",
    padding: "0",
  } as CSSStyleDeclaration);
  closeBtn.addEventListener("click", () => {
    panel?.remove();
    if (state.onClose) state.onClose();
  });
  header.appendChild(closeBtn);
  panel.appendChild(header);

  if (state.body) {
    const bodyEl = document.createElement("div");
    bodyEl.style.fontSize = "11px";
    bodyEl.style.color = "rgba(250,250,250,0.7)";
    bodyEl.textContent = state.body;
    panel.appendChild(bodyEl);
  }

  if (state.comment) {
    const box = document.createElement("div");
    Object.assign(box.style, {
      padding: "10px 12px",
      borderRadius: "10px",
      background: "rgba(34, 211, 238, 0.06)",
      border: "1px solid rgba(34, 211, 238, 0.18)",
      color: "#e2e8f0",
      whiteSpace: "pre-wrap",
      fontSize: "12px",
      maxHeight: "240px",
      overflowY: "auto",
    } as CSSStyleDeclaration);
    box.textContent = state.comment;
    panel.appendChild(box);

    const row = document.createElement("div");
    Object.assign(row.style, {
      display: "flex",
      gap: "8px",
    } as CSSStyleDeclaration);

    const copyBtn = document.createElement("button");
    copyBtn.textContent = "Copiar comentario";
    Object.assign(copyBtn.style, {
      flex: "1",
      padding: "8px 12px",
      borderRadius: "8px",
      background: "linear-gradient(135deg, #22d3ee, #a3e635)",
      color: "#0a0a0a",
      border: "none",
      fontWeight: "600",
      fontSize: "12px",
      cursor: "pointer",
    } as CSSStyleDeclaration);
    copyBtn.addEventListener("click", async () => {
      if (!state.comment) return;
      try {
        await navigator.clipboard.writeText(state.comment);
        copyBtn.textContent = "Copiado ✓";
        setTimeout(() => (copyBtn.textContent = "Copiar comentario"), 2000);
      } catch {
        copyBtn.textContent = "Error al copiar";
      }
      state.onCopy?.();
    });
    row.appendChild(copyBtn);

    const regenBtn = document.createElement("button");
    regenBtn.textContent = "Regenerar";
    Object.assign(regenBtn.style, {
      padding: "8px 12px",
      borderRadius: "8px",
      background: "transparent",
      color: "#cbd5e1",
      border: "1px solid rgba(255,255,255,0.1)",
      fontSize: "12px",
      cursor: "pointer",
    } as CSSStyleDeclaration);
    regenBtn.addEventListener("click", () => {
      state.onRegenerate?.();
    });
    row.appendChild(regenBtn);

    panel.appendChild(row);
  }
}

// ---------------------------------------------------------------------------
// Action
// ---------------------------------------------------------------------------

function isExtensionInvalidated(err: unknown): boolean {
  const msg = (err as Error)?.message ?? String(err);
  return /Extension context invalidated|receiving end does not exist/i.test(msg);
}

function showRecoveryPanel(): void {
  showPanel({
    status: "JobHunter desactualizado",
    body:
      "La extensión se recargó mientras esta pestaña estaba abierta.\n\n" +
      "Pulsa F5 (Cmd+R) en esta pestaña para reactivarla. Después vuelve a pulsar el pill.",
  });
}

async function suggestForCurrentPost(): Promise<void> {
  const extracted = extractPost();
  if (!extracted) {
    showPanel({
      status: "No detecto un post",
      body:
        "No encuentro suficiente texto visible en esta página. Abre el post (click en el título) y vuelve a pulsar.",
    });
    return;
  }
  showPanel({
    status: "Generando con Claude…",
    body: `Autor detectado: ${extracted.author_name}\nLongitud del post: ${extracted.content.length} caracteres`,
  });
  try {
    if (!chrome.runtime?.id) {
      showRecoveryPanel();
      return;
    }
    const resp = await chrome.runtime.sendMessage({
      type: "GENERATE_COMMENT_FOR_POST",
      payload: {
        post_url: extracted.url,
        author_name: extracted.author_name,
        author_headline: extracted.author_headline,
        content_excerpt: extracted.content,
        language: extracted.language,
      },
    });
    if (!resp?.success || !resp.data?.suggested_comment) {
      showPanel({
        status: "Sin sugerencia",
        body:
          resp?.error ??
          "Claude no devolvió un comentario relevante para este post.",
        onRegenerate: suggestForCurrentPost,
      });
      return;
    }
    showPanel({
      status: "Comentario sugerido",
      comment: resp.data.suggested_comment,
      onRegenerate: suggestForCurrentPost,
    });
  } catch (e) {
    if (isExtensionInvalidated(e)) {
      showRecoveryPanel();
      return;
    }
    showPanel({
      status: "Error",
      body: (e as Error).message,
      onRegenerate: suggestForCurrentPost,
    });
  }
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

function boot() {
  if (!isLikelyPostPage()) return;
  log.info("[post-helper] mounted on", location.href);
  mountPill(() => {
    suggestForCurrentPost().catch((e) => log.error("suggest failed", e));
  });
}

// Mount immediately + survive SPA navigation
boot();
window.addEventListener("DOMContentLoaded", boot);
setInterval(() => {
  if (!document.getElementById(PILL_ID)) boot();
}, 3000);
