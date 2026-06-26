// Helpers DOM compartidos por los content scripts.
// Diseñados para imitar interacción humana razonable.

export function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

export function humanDelay(): Promise<void> {
  return sleep(200 + Math.random() * 600);
}

export function shortDelay(): Promise<void> {
  return sleep(80 + Math.random() * 180);
}

export async function waitFor<E extends Element = Element>(
  selector: string,
  timeout = 10_000,
  root: ParentNode = document
): Promise<E> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const el = root.querySelector<E>(selector);
    if (el) return el;
    await sleep(200);
  }
  throw new Error(`Timeout esperando selector "${selector}"`);
}

export async function waitForAny<E extends Element = Element>(
  selectors: string[],
  timeout = 10_000,
  root: ParentNode = document
): Promise<E> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    for (const sel of selectors) {
      const el = root.querySelector<E>(sel);
      if (el) return el;
    }
    await sleep(200);
  }
  throw new Error(`Timeout esperando selectores [${selectors.join(", ")}]`);
}

/**
 * Busca un botón cuyo texto, aria-label o título contenga alguna de las
 * variantes dadas. Útil para soportar LinkedIn en ES e EN.
 */
export async function waitForText(
  variants: string | string[],
  timeout = 10_000
): Promise<HTMLElement> {
  const arr = Array.isArray(variants) ? variants : [variants];
  const lowered = arr.map((v) => v.toLowerCase());

  const start = Date.now();
  while (Date.now() - start < timeout) {
    const found = findByText(lowered);
    if (found) return found;
    await sleep(200);
  }
  throw new Error(`Timeout esperando texto "${arr.join(" | ")}"`);
}

export function findByText(lowered: string[]): HTMLElement | null {
  const candidates = Array.from(
    document.querySelectorAll<HTMLElement>(
      'button, [role="button"], a, span'
    )
  );
  for (const el of candidates) {
    const text = (el.textContent ?? "").trim().toLowerCase();
    const aria = (el.getAttribute("aria-label") ?? "").toLowerCase();
    const title = (el.getAttribute("title") ?? "").toLowerCase();
    if (
      lowered.some(
        (v) => text.includes(v) || aria.includes(v) || title.includes(v)
      )
    ) {
      // Subimos al ancestro clickable si el match cayó en span
      const clickable = el.closest<HTMLElement>(
        'button, [role="button"], a'
      );
      return clickable ?? el;
    }
  }
  return null;
}

export async function humanClick(el: Element): Promise<void> {
  el.scrollIntoView({ block: "center", behavior: "smooth" });
  await sleep(100 + Math.random() * 200);
  (el as HTMLElement).click();
  await humanDelay();
}

/**
 * Escribe carácter a carácter respetando el setter nativo de React/LinkedIn.
 * Usamos el setter del prototipo porque LinkedIn re-escribe inputs con React.
 */
export async function humanType(
  el: HTMLTextAreaElement | HTMLInputElement | HTMLElement,
  text: string
): Promise<void> {
  el.focus();
  await shortDelay();

  // contenteditable (el editor de posts de LinkedIn usa esto)
  if ((el as HTMLElement).isContentEditable) {
    const target = el as HTMLElement;
    for (const char of text) {
      document.execCommand("insertText", false, char);
      target.dispatchEvent(new InputEvent("input", { bubbles: true, data: char }));
      await sleep(15 + Math.random() * 70);
    }
    target.dispatchEvent(new Event("change", { bubbles: true }));
    return;
  }

  const target = el as HTMLInputElement | HTMLTextAreaElement;
  const proto = target instanceof HTMLTextAreaElement
    ? HTMLTextAreaElement.prototype
    : HTMLInputElement.prototype;
  const nativeSetter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
  let buffer = target.value ?? "";

  for (const char of text) {
    buffer += char;
    if (nativeSetter) {
      nativeSetter.call(target, buffer);
    } else {
      target.value = buffer;
    }
    target.dispatchEvent(new Event("input", { bubbles: true }));
    await sleep(20 + Math.random() * 80);
  }
  target.dispatchEvent(new Event("change", { bubbles: true }));
}

/**
 * Espera a que el documento esté completamente cargado y sin spinners
 * de LinkedIn visibles.
 */
export async function waitForPageReady(timeout = 15_000): Promise<void> {
  if (document.readyState !== "complete") {
    await new Promise<void>((resolve) => {
      window.addEventListener("load", () => resolve(), { once: true });
    });
  }
  // Espera adicional defensiva para SPAs como LinkedIn
  await sleep(500 + Math.random() * 600);
  // Si LinkedIn muestra spinners globales, intenta esperar a que desaparezcan
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const spinner = document.querySelector(
      '.artdeco-loader, .loading-bar, [aria-busy="true"]'
    );
    if (!spinner) return;
    await sleep(250);
  }
}

export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Partial<Record<string, string>> = {},
  children: (Node | string)[] = []
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else node.setAttribute(k, v);
  }
  for (const c of children) {
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}
