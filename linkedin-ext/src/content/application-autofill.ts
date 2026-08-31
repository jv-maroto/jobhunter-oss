// Universal application form auto-filler.
//
// Detects common job-application form fields on Wellfound, Lever, Greenhouse,
// Workable, Ashby, Welcome to the Jungle and similar ATS pages, then fills them
// with the user's profile pulled from /ext/profile.
//
// Strategy:
//   1. Fetch profile once and cache in chrome.storage.session.
//   2. Mutation-observe the DOM. When a form with email/name appears, show
//      a floating "JobHunter · Auto-fill" pill in the bottom-right.
//   3. On click, scan inputs by name / id / aria-label / placeholder /
//      surrounding label text, score each candidate against a field-rule table,
//      and set the value using React's native value setter so controlled inputs
//      pick the change up.
//
// The user keeps full control: nothing is submitted automatically.

import { humanType, sleep } from "../lib/dom";

type FieldKey =
  | "first_name"
  | "last_name"
  | "full_name"
  | "email"
  | "phone"
  | "linkedin_url"
  | "github_url"
  | "portfolio_url"
  | "location"
  | "city"
  | "country"
  | "academic_degree"
  | "graduation_date"
  | "current_role"
  | "current_company"
  | "years_experience"
  | "salary_expectation"
  | "work_authorization_eu"
  | "willing_to_relocate"
  | "remote_preference"
  | "notice_period"
  | "languages"
  | "summary"
  | "experience_narrative"
  | "frontend_showcase"
  | "backend_showcase"
  | "production_system_story"
  | "cover_letter_generic"
  // Synthetic keys: do not match anything in Profile, value is provided inline.
  | "__skip__"
  | "__answer_no__"
  | "__answer_yes__";

type Profile = Record<
  Exclude<FieldKey, "__skip__" | "__answer_no__" | "__answer_yes__">,
  string | boolean | number
>;

interface FieldRule {
  key: FieldKey;
  patterns: RegExp[];
  /** Higher = checked first when multiple match. */
  priority?: number;
  /** Optional inline override; if returns null, the field is skipped. */
  inline?: string | boolean;
}

const RULES: FieldRule[] = [
  // ===== SKIP (never autofill) =====
  {
    key: "__skip__",
    priority: 1000,
    patterns: [
      /\bpassword\b/i,
      /\bconfirm password\b/i,
      /\bset (a |your )?password\b/i,
      /\bcaptcha\b/i,
      /\bcredit card\b/i,
      /\bcard number\b/i,
      /\bssn\b/i,
      /\bdate of birth\b/i,
    ],
  },

  // ===== US-SPECIFIC AUTH (you are NOT US-authorized) =====
  {
    key: "__answer_no__",
    priority: 950,
    patterns: [
      /\bU\.?S\.? work authoriz/i,
      /\b(?:authori[sz]ed|authoriz)\b.*\bunited states\b/i,
      /\blegally authoriz.*united states\b/i,
      /\beligible to work in the (?:US|United States)\b/i,
    ],
  },

  // ===== US-SPECIFIC SPONSORSHIP (you DO need sponsorship to work in US) =====
  {
    key: "__answer_yes__",
    priority: 940,
    patterns: [
      /\b(?:require|need)\s+(?:sponsorship|visa)\b.*\b(?:us|united states)\b/i,
      /\bsponsorship\b.*\b(?:H-?1B|us employment|united states)\b/i,
      /\bH-?1B\b/i,
    ],
  },

  // ===== EU / "any of these EU countries" auth (Yes) =====
  {
    key: "__answer_yes__",
    priority: 930,
    patterns: [
      /\b(?:legally )?(?:able to )?work\b.*\b(?:spain|france|portugal|germany|italy|netherlands|belgium|ireland|austria|sweden|denmark|finland|poland|EU|european union)\b/i,
      /\beligible to work in\b.*\b(?:spain|europe|the eu|france|portugal|germany|italy)\b/i,
      /\bEU (?:citizen|national|resident)\b/i,
      /\bwork (?:permit|authoriz).*(?:EU|European Union|Spain|Europe)\b/i,
    ],
  },

  // ===== Based in / willing to relocate to EU country (Yes) =====
  {
    key: "__answer_yes__",
    priority: 920,
    patterns: [
      /\b(?:based in|willing to relocate).*\b(?:spain|france|portugal|germany|italy|belgium|netherlands|EU|europe)\b/i,
      /\bcurrently based in.*\b(?:spain|europe|france|portugal)\b/i,
    ],
  },

  // ===== Minimum N years experience — answer Yes if N <= your years =====
  // Your years of experience come from cv_master.json; the exact comparison
  // happens at fill time.
  {
    key: "__answer_yes__",
    priority: 910,
    patterns: [
      /\bminimum of (?:1|2|3|4) years? of experience\b/i,
      /\bat least (?:1|2|3|4) years? of experience\b/i,
      /\b(?:1|2|3|4)\+? years? of experience\b/i,
    ],
  },

  // ===== contact =====
  { key: "email", patterns: [/\bemail\b/i, /\be[-]?mail address\b/i], priority: 100 },
  { key: "phone", patterns: [/\bphone\b/i, /\btelephone\b/i, /\bmobile\b/i, /\btel\b/i] },

  // ===== identity =====
  {
    key: "full_name",
    priority: 50,
    patterns: [/^name$/i, /\bfull name\b/i, /\byour name\b/i, /\bcandidate name\b/i, /\bnombre completo\b/i],
  },
  {
    key: "first_name",
    priority: 40,
    patterns: [/\bfirst name\b/i, /\bgiven name\b/i, /\bfirst[_-]?name\b/i, /\bnombre\b/i],
  },
  {
    key: "last_name",
    priority: 40,
    patterns: [
      /\blast name\b/i,
      /\bsurname\b/i,
      /\bfamily name\b/i,
      /\blast[_-]?name\b/i,
      /\bapellidos?\b/i,
    ],
  },

  // ===== links =====
  { key: "linkedin_url", patterns: [/\blinkedin\b/i] },
  { key: "github_url", patterns: [/\bgithub\b/i] },
  {
    key: "portfolio_url",
    patterns: [
      /\bportfolio\b/i,
      /\bpersonal (site|website)\b/i,
      /\bpersonal url\b/i,
      /\bweb(?:site)?\b/i,
    ],
  },

  // ===== location =====
  {
    key: "location",
    patterns: [
      /\b(?:set your |your )?location\b/i,
      /\bbased in\b/i,
      /\bdonde vives\b/i,
      /\bubicaci/i,
      /\b(?:current )?domicile\b/i,
      /\bdomicilio\b/i,
      /\bresidencia\b/i,
    ],
  },
  { key: "city", patterns: [/\bcity\b/i, /\btown\b/i, /\bciudad\b/i] },
  { key: "country", patterns: [/\bcountry\b/i, /\bpa[ií]s\b/i] },

  // ===== education =====
  {
    key: "academic_degree",
    priority: 35,
    patterns: [
      /\bacademic degree\b/i,
      /\bhighest (?:degree|qualification|education)\b/i,
      /\bdegree (?:name|obtained)\b/i,
      /\bfield of study\b/i,
      /\bt[íi]tulo (?:acad[ée]mico|universitario)\b/i,
      /\btitulaci[óo]n\b/i,
    ],
  },
  {
    key: "graduation_date",
    priority: 35,
    patterns: [
      /\b(?:estimated |expected )?graduation date\b/i,
      /\bgraduation year\b/i,
      /\bexpected graduation\b/i,
      /\bfecha de graduaci[óo]n\b/i,
    ],
  },

  // ===== employment =====
  {
    key: "current_role",
    patterns: [/\bcurrent (role|position|title|job)\b/i, /\bcurrent title\b/i, /\bpuesto actual\b/i],
  },
  {
    key: "current_company",
    patterns: [/\bcurrent company\b/i, /\bcurrent employer\b/i, /\bempresa actual\b/i],
  },
  {
    key: "years_experience",
    patterns: [/\byears? of (experience|exp)\b/i, /\byoe\b/i, /\baños? de experiencia\b/i],
  },
  {
    key: "salary_expectation",
    patterns: [
      /\bsalary\b/i,
      /\bdesired (?:pay|salary|compensation)\b/i,
      /\bexpected (?:pay|compensation|salary)\b/i,
      /\bcompensation\b/i,
      /\brate\b/i,
      /\bsalario\b/i,
    ],
  },
  { key: "willing_to_relocate", patterns: [/\brelocat/i, /\bmudarse\b/i] },
  { key: "remote_preference", patterns: [/\bwork from home\b/i, /\bremote preference\b/i] },
  {
    key: "notice_period",
    patterns: [/\bnotice period\b/i, /\bavailable to start\b/i, /\bstart date\b/i, /\bdisponibilidad\b/i],
  },
  { key: "languages", patterns: [/\blanguages?\b/i, /\bidiomas?\b/i] },

  // ===== narrative — production system story (Django/FastAPI/Flask architecture) =====
  // Higher than experience_narrative so the more specific match wins.
  {
    key: "production_system_story",
    priority: 45,
    patterns: [
      /\b(?:real|production) system .* (?:django|fastapi|flask)\b/i,
      /\b(?:django|fastapi|flask).{0,40}\bin production\b/i,
      /\barchitecture\b.*\b(?:django|fastapi|flask)\b/i,
      /\bhow (?:did|do) you (?:scale|handle (?:scaling|failures))\b/i,
      /\bexplain (?:the |your )?architecture\b/i,
      /\bsystem design\b.{0,80}\bproduction\b/i,
    ],
  },

  // ===== narrative — frontend showcase =====
  {
    key: "frontend_showcase",
    priority: 42,
    patterns: [
      /\bmost (?:impressive|notable|interesting|complex) frontend\b/i,
      /\bbest frontend (?:work|project)\b/i,
      /\b(?:share|show|link to)?\s*your (?:best )?frontend (?:work|project)\b/i,
      /\bfrontend work you('?ve| have)? done\b/i,
      /\bmejor (?:trabajo |proyecto )?frontend\b/i,
    ],
  },

  // ===== narrative — backend showcase =====
  {
    key: "backend_showcase",
    priority: 42,
    patterns: [
      /\bmost (?:impressive|notable|interesting|complex) backend\b/i,
      /\bbest backend (?:work|project)\b/i,
      /\b(?:share|show|link to)?\s*your (?:best )?backend (?:work|project)\b/i,
      /\bbackend work you('?ve| have)? done\b/i,
      /\bmejor (?:trabajo |proyecto )?backend\b/i,
    ],
  },

  // ===== narrative — experience description =====
  // Long-form questions about background, experience, stack, projects.
  // Higher priority than summary so "tell us about your experience" wins over
  // the more generic "tell us about you".
  {
    key: "experience_narrative",
    priority: 30,
    patterns: [
      /\btell us about your (?:experience|background|work|role|projects|career)\b/i,
      /\bhow many years.{0,80}\bexperience\b/i,
      /\b(?:describe|share|walk (?:us|me) through) your (?:experience|background|work)\b/i,
      /\babout your experience\b/i,
      /\babout your background\b/i,
      /\byour experience (?:as|with|in)\b/i,
      /\bhighlight (?:some of )?(?:the )?(?:projects|technologies|stack)\b/i,
      /\btechnologies you('?ve| have)? worked with\b/i,
      /\bprojects you('?ve| have)? worked on\b/i,
      /\bbriefly describe\b/i,
      /\bcu[ée]ntanos sobre tu experiencia\b/i,
      /\bdescribe tu experiencia\b/i,
      /\btu experiencia (?:como|con|en)\b/i,
    ],
  },
  // ===== narrative — generic "about you" / summary =====
  {
    key: "summary",
    patterns: [
      /\babout you\b(?!r)/i,           // "about you" but not "about your X"
      /\bsummary\b/i,
      /\bbio\b/i,
      /\btell us about you\b(?!r)/i,
      /\bwho are you\b/i,
      /\bintroduce yourself\b/i,
      /\bsobre ti\b/i,
      /\bpresent[áa]te\b/i,
    ],
  },
  {
    key: "cover_letter_generic",
    patterns: [
      /\bcover letter\b/i,
      /\bwhy (?:do you|are you) (?:want|interested)\b/i,
      /\bwhy this (?:role|company|position)\b/i,
      /\bwhat interests you\b/i,
      /\bwhat (?:excites|attracts|draws) you\b/i,
      /\bmotivation\b/i,
      /\badditional information\b/i,
      /\banything (?:else|we should know)\b/i,
      /\bmessage to (?:employer|hiring|the team)\b/i,
      /\bquieres trabajar\b/i,
      /\bpor qu[ée] (?:te interesa|quieres|aplicas)\b/i,
    ],
  },
];

const STORAGE_KEY = "jobhunter_profile";
const STORAGE_TTL_MS = 1000 * 60 * 60; // 1h

async function loadProfile(): Promise<Profile | null> {
  // Try cache first
  try {
    const cached = await chrome.storage.session.get(STORAGE_KEY);
    const entry = cached[STORAGE_KEY];
    if (entry && Date.now() - entry.fetched_at < STORAGE_TTL_MS) {
      return entry.data as Profile;
    }
  } catch {
    /* session storage may not exist */
  }
  if (!chrome.runtime?.id) {
    console.log(`${ORIGIN_TAG} extension context invalidated — please F5 to reactivate`);
    return null;
  }
  try {
    const response = await chrome.runtime.sendMessage({ type: "GET_PROFILE" });
    if (!response?.success || !response.data) {
      console.log(
        `${ORIGIN_TAG} GET_PROFILE failed`,
        response?.error ?? "no response",
      );
      return null;
    }
    const data = response.data as Profile;
    try {
      await chrome.storage.session.set({
        [STORAGE_KEY]: { data, fetched_at: Date.now() },
      });
    } catch {
      /* ignore */
    }
    return data;
  } catch (e) {
    const msg = (e as Error).message;
    if (/Extension context invalidated/i.test(msg)) {
      console.log(`${ORIGIN_TAG} extension reloaded — please F5 to reactivate`);
    } else {
      console.log(`${ORIGIN_TAG} sendMessage failed`, msg);
    }
    return null;
  }
}

/** Build descriptive text strings for an input, in *layers* of decreasing
 *  specificity. We try to match against the most specific layer first to
 *  avoid being confused by neighbouring fields' labels. */
function describeLayers(
  el: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement,
): string[] {
  const layers: string[][] = [[], [], [], []];
  const push = (idx: number, s?: string | null) => {
    if (!s) return;
    const t = s.trim().slice(0, 250);
    if (t) layers[idx].push(t);
  };

  // Layer 0: input's own attributes — strongest signal
  push(0, el.name);
  push(0, el.id);
  push(0, el.getAttribute("aria-label"));
  push(0, el.getAttribute("data-test"));
  push(0, el.getAttribute("data-testid"));
  push(0, el.getAttribute("data-qa"));
  push(0, (el as HTMLInputElement).placeholder);
  push(0, (el as HTMLInputElement).autocomplete);
  push(0, el.getAttribute("title"));
  push(0, (el as HTMLInputElement).type);

  // Layer 1: closest <label> for the input
  if (el.id) {
    try {
      const label = el.ownerDocument.querySelector(
        `label[for="${CSS.escape(el.id)}"]`,
      );
      push(1, label?.textContent ?? null);
    } catch {
      /* ignore */
    }
  }
  push(1, el.closest("label")?.textContent ?? null);

  // aria-labelledby references
  const labelledBy = el.getAttribute("aria-labelledby");
  if (labelledBy) {
    for (const id of labelledBy.split(/\s+/)) {
      try {
        const r = el.ownerDocument.getElementById(id);
        push(1, r?.textContent ?? null);
      } catch {
        /* ignore */
      }
    }
  }

  // Layer 2: immediate previous siblings (typical "<div>Label</div><input/>")
  let prev = el.previousElementSibling;
  let pcount = 0;
  while (prev && pcount < 3) {
    const txt = (prev as HTMLElement).innerText ?? prev.textContent ?? "";
    if (txt && txt.length < 200) push(2, txt);
    prev = prev.previousElementSibling;
    pcount += 1;
  }

  // Layer 3: closest ancestor that looks like a field container,
  // taking ONLY its first/leading text (typical "<div><h3>Label</h3><input/></div>")
  let parent: HTMLElement | null = el.parentElement;
  let depth = 0;
  while (parent && depth < 3) {
    // Take the FIRST short text node / heading inside the parent that's not our input subtree
    for (const child of Array.from(parent.children)) {
      if (child === el || child.contains(el)) continue;
      const tag = child.tagName.toLowerCase();
      if (["input", "textarea", "select"].includes(tag)) break; // stop, sibling form field
      const txt = ((child as HTMLElement).innerText ?? child.textContent ?? "")
        .trim()
        .slice(0, 150);
      if (txt) {
        push(3, txt);
        break; // only the first text per parent
      }
    }
    parent = parent.parentElement;
    depth += 1;
  }

  return layers.map((arr) => arr.join(" || ").toLowerCase()).filter(Boolean);
}

function matchRule(layers: string[]): FieldRule | null {
  const ordered = [...RULES].sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));
  // Try each layer (most specific first). Rules with very high priority
  // (skip, US-specific) match in ANY layer; field-match rules require the
  // signal to appear in a specific layer to avoid cross-talk.
  for (let i = 0; i < layers.length; i += 1) {
    const layer = layers[i];
    if (!layer) continue;
    for (const rule of ordered) {
      // Skip / special rules only fire if they match the FIRST 2 layers
      // (input itself or its label). Otherwise neighboring "password" field
      // could nuke unrelated inputs.
      const isSpecial = rule.key.startsWith("__");
      if (isSpecial && i >= 2) continue;
      if (rule.patterns.some((p) => p.test(layer))) {
        return rule;
      }
    }
  }
  return null;
}

function setNativeValue(el: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const proto = Object.getPrototypeOf(el);
  const desc = Object.getOwnPropertyDescriptor(proto, "value");
  desc?.set?.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
}

async function fillField(
  el: HTMLInputElement | HTMLTextAreaElement,
  raw: string | boolean | number,
): Promise<void> {
  const value = typeof raw === "boolean" ? (raw ? "Yes" : "No") : String(raw);
  if (!value) return;
  el.focus();
  if (el.tagName === "TEXTAREA" && value.length > 80) {
    // Type long text humanly so React forms validate properly
    await humanType(el as HTMLTextAreaElement, value);
  } else {
    setNativeValue(el, value);
  }
}

function trySelectOption(el: HTMLSelectElement, raw: string | boolean | number): boolean {
  const target =
    typeof raw === "boolean"
      ? raw
        ? "yes"
        : "no"
      : String(raw).toLowerCase();
  const options = Array.from(el.options);
  // Exact match first
  let opt = options.find((o) => o.value.toLowerCase() === target || o.text.toLowerCase() === target);
  // Fuzzy contains
  if (!opt) opt = options.find((o) => o.text.toLowerCase().includes(target));
  if (!opt) return false;
  el.value = opt.value;
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

interface AutoFillResult {
  filled: number;
  skipped: number;
  byKey: Record<string, number>;
}

/** Walks the whole document AND any open shadow roots. */
function collectFields(): Array<
  HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
> {
  const out: Array<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement> = [];
  const walk = (root: Document | ShadowRoot) => {
    out.push(
      ...Array.from(
        root.querySelectorAll<
          HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
        >("input, textarea, select"),
      ),
    );
    root.querySelectorAll<HTMLElement>("*").forEach((el) => {
      const sr = (el as Element & { shadowRoot?: ShadowRoot | null })
        .shadowRoot;
      if (sr) walk(sr);
    });
  };
  walk(document);
  return out;
}

function visibleAndEditable(
  el: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement,
): boolean {
  if (el.disabled) return false;
  if ((el as HTMLInputElement).readOnly) return false;
  const type = (el as HTMLInputElement).type;
  if (["hidden", "submit", "button", "file", "image"].includes(type)) return false;
  const rect = el.getBoundingClientRect();
  if (rect.width < 1 || rect.height < 1) return false;
  const style = getComputedStyle(el);
  if (style.display === "none" || style.visibility === "hidden") return false;
  return true;
}

function valueForRule(
  rule: FieldRule,
  profile: Profile,
): string | boolean | number | null {
  if (rule.key === "__skip__") return null;
  if (rule.key === "__answer_no__") return "No";
  if (rule.key === "__answer_yes__") return "Yes";
  const v = (profile as Record<string, string | boolean | number>)[rule.key];
  if (v === undefined || v === null || v === "") return null;
  return v;
}

/** Try to click a Yes/No control near `from`. Supports native radios AND
 *  custom buttons / divs that contain the literal text "Yes" / "No". */
function tryClickYesNo(
  from: HTMLElement,
  desired: "Yes" | "No",
): boolean {
  const desiredLower = desired.toLowerCase();
  let scope: HTMLElement | null = from.parentElement;
  for (let i = 0; i < 8 && scope; i += 1) {
    // 1) Native radios
    const radios = Array.from(
      scope.querySelectorAll<HTMLInputElement>(
        'input[type="radio"], [role="radio"]',
      ),
    );
    if (radios.length >= 2) {
      const target = radios.find((r) => {
        const lbl = (
          (r.closest("label")?.textContent ?? "") +
          " " +
          (r.getAttribute("aria-label") ?? "") +
          " " +
          (r.parentElement?.textContent ?? "")
        )
          .trim()
          .toLowerCase();
        return lbl.startsWith(desiredLower) || lbl === desiredLower;
      });
      if (target) {
        (target as HTMLElement).click();
        target.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
    }

    // 2) Buttons / divs with literal "Yes" / "No" text
    const clickables = Array.from(
      scope.querySelectorAll<HTMLElement>(
        'button, [role="button"], div[tabindex], li, label',
      ),
    );
    const target = clickables.find((b) => {
      const t = (b.innerText ?? b.textContent ?? "").trim().toLowerCase();
      return t === desiredLower;
    });
    if (target && target !== from) {
      target.click();
      target.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    }

    scope = scope.parentElement;
  }
  return false;
}

/** Find Yes/No question groups that have NO associated input (Alan style):
 *  the question is in headings/paragraphs and the answers are plain buttons. */
function findOrphanYesNoGroups(): Array<{
  context: string;
  yesBtn: HTMLElement;
  noBtn: HTMLElement;
  signature: string;
}> {
  const out: Array<{
    context: string;
    yesBtn: HTMLElement;
    noBtn: HTMLElement;
    signature: string;
  }> = [];

  // Find every "Yes" button candidate
  const yesCandidates = Array.from(
    document.querySelectorAll<HTMLElement>(
      'button, [role="button"], label',
    ),
  ).filter((b) => {
    const t = (b.innerText ?? b.textContent ?? "").trim().toLowerCase();
    return t === "yes";
  });

  for (const yesBtn of yesCandidates) {
    // Walk up to find a parent that ALSO has a sibling "No"
    let scope: HTMLElement | null = yesBtn.parentElement;
    for (let i = 0; i < 5 && scope; i += 1) {
      const noBtn = Array.from(
        scope.querySelectorAll<HTMLElement>('button, [role="button"], label'),
      ).find((b) => {
        const t = (b.innerText ?? b.textContent ?? "").trim().toLowerCase();
        return t === "no";
      });
      if (noBtn && noBtn !== yesBtn) {
        // Question text = the scope's text minus "Yes" + "No"
        const fullText = (scope.innerText ?? scope.textContent ?? "")
          .trim()
          .toLowerCase()
          .replace(/\byes\b/g, "")
          .replace(/\bno\b/g, "")
          .slice(0, 400);
        const signature = fullText.slice(0, 100);
        if (!out.some((g) => g.signature === signature)) {
          out.push({ context: fullText, yesBtn, noBtn, signature });
        }
        break;
      }
      scope = scope.parentElement;
    }
  }
  return out;
}

async function autoFillForm(profile: Profile): Promise<AutoFillResult> {
  const result: AutoFillResult = { filled: 0, skipped: 0, byKey: {} };
  const seen = new WeakSet<Element>();

  const candidates = collectFields().filter(visibleAndEditable);

  for (const el of candidates) {
    if (seen.has(el)) continue;
    seen.add(el);

    const layers = describeLayers(el);
    if (layers.length === 0) continue;

    const rule = matchRule(layers);
    if (!rule) {
      result.skipped += 1;
      console.log(
        "[JobHunter] no rule for input",
        layers.join(" / ").slice(0, 200),
      );
      continue;
    }
    const value = valueForRule(rule, profile);
    if (value === null) {
      result.skipped += 1;
      continue;
    }

    // Yes/No questions often render as radios or custom buttons (Alan style).
    if (value === "Yes" || value === "No") {
      if (tryClickYesNo(el as HTMLElement, value as "Yes" | "No")) {
        result.filled += 1;
        result.byKey[rule.key] = (result.byKey[rule.key] ?? 0) + 1;
        continue;
      }
    }

    try {
      if (el.tagName === "SELECT") {
        if (trySelectOption(el as HTMLSelectElement, value)) {
          result.filled += 1;
          result.byKey[rule.key] = (result.byKey[rule.key] ?? 0) + 1;
        } else {
          result.skipped += 1;
        }
        continue;
      }
      const realValue = String(value);
      await fillField(el as HTMLInputElement | HTMLTextAreaElement, realValue);
      result.filled += 1;
      result.byKey[rule.key] = (result.byKey[rule.key] ?? 0) + 1;
      await sleep(40);
    } catch {
      result.skipped += 1;
    }
  }

  // Second pass: orphan Yes/No question groups (buttons without input)
  const groups = findOrphanYesNoGroups();
  for (const g of groups) {
    const rule = matchRule([g.context]);
    if (!rule) {
      result.skipped += 1;
      continue;
    }
    const value = valueForRule(rule, profile);
    if (value !== "Yes" && value !== "No") {
      result.skipped += 1;
      continue;
    }
    const target = value === "Yes" ? g.yesBtn : g.noBtn;
    try {
      target.click();
      target.dispatchEvent(new Event("change", { bubbles: true }));
      result.filled += 1;
      result.byKey[rule.key] = (result.byKey[rule.key] ?? 0) + 1;
      await sleep(60);
    } catch {
      result.skipped += 1;
    }
  }

  return result;
}

// ---------------------------------------------------------------------------
// Floating "JobHunter · Auto-fill" overlay
// ---------------------------------------------------------------------------

const OVERLAY_ID = "jobhunter-autofill-overlay";

function mountOverlay(onFill: () => Promise<AutoFillResult>): void {
  if (document.getElementById(OVERLAY_ID)) return;

  const root = document.createElement("div");
  root.id = OVERLAY_ID;
  Object.assign(root.style, {
    position: "fixed",
    right: "20px",
    bottom: "20px",
    zIndex: "2147483646",
    fontFamily:
      'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  } as CSSStyleDeclaration);

  const pill = document.createElement("button");
  Object.assign(pill.style, {
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
    fontSize: "12px",
    fontWeight: "600",
    cursor: "pointer",
    letterSpacing: "0.02em",
  } as CSSStyleDeclaration);
  pill.innerHTML = `
    <span style="
      display:inline-block;width:8px;height:8px;border-radius:50%;
      background:#22d3ee;box-shadow:0 0 8px #22d3ee;
    "></span>
    JobHunter · Auto-fill this form
  `;

  const note = document.createElement("div");
  Object.assign(note.style, {
    marginTop: "8px",
    padding: "6px 10px",
    borderRadius: "8px",
    background: "rgba(11, 14, 22, 0.85)",
    color: "rgba(250,250,250,0.7)",
    border: "1px solid rgba(255,255,255,0.08)",
    fontSize: "10.5px",
    maxWidth: "260px",
    textAlign: "right",
    display: "none",
  } as CSSStyleDeclaration);

  pill.addEventListener("click", async () => {
    pill.disabled = true;
    pill.innerHTML = "Filling…";
    try {
      const result = await onFill();
      pill.innerHTML = `Filled ${result.filled} fields`;
      note.textContent = `Detected: ${Object.keys(result.byKey).join(", ") || "—"}. Skipped: ${result.skipped}. Review and submit yourself.`;
      note.style.display = "block";
      setTimeout(() => {
        pill.innerHTML = `
          <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#22d3ee;box-shadow:0 0 8px #22d3ee;"></span>
          JobHunter · Re-fill form
        `;
        pill.disabled = false;
      }, 2500);
    } catch (e) {
      pill.innerHTML = `Error: ${(e as Error).message.slice(0, 80)}`;
      setTimeout(() => {
        pill.innerHTML = "Retry auto-fill";
        pill.disabled = false;
      }, 4000);
    }
  });

  root.append(pill, note);
  document.body.appendChild(root);
}

// ---------------------------------------------------------------------------
// Mounting strategy:
// Always show the floating pill on any ATS page in our manifest matches.
// User decides when to click it. We rely on collectFields() (which walks
// shadow DOMs) to find the modal inputs at click time.
// ---------------------------------------------------------------------------

const IS_TOP = window === window.top;
const ORIGIN_TAG = `[JobHunter][${IS_TOP ? "top" : "iframe"}][${location.host}]`;

// Solo aceptamos disparadores de autofill entre frames si el frame padre está
// en un origen ATS/JobHunter conocido. Sin esto, una web atacante podría
// embeber un formulario de solicitud real en un <iframe> y hacerle postMessage
// para rellenar en silencio los datos personales de la víctima (clickjacking).
const TRUSTED_ORIGIN_RE =
  /^https:\/\/([a-z0-9-]+\.)*(linkedin\.com|wellfound\.com|angel\.co|lever\.co|greenhouse\.io|ashbyhq\.com|workable\.com|welcometothejungle\.com|otta\.com|teamtailor\.com|smartrecruiters\.com|recruitee\.com|jazz\.co|jazzhr\.com|personio\.(com|de)|myworkdayjobs\.com|icims\.com|bamboohr\.com|breezy\.hr|factorialhr\.com|pinpointhq\.com|indeed\.com|talentclue\.com)$/i;

function isTrustedFrameOrigin(origin: string): boolean {
  return TRUSTED_ORIGIN_RE.test(origin);
}

let mounted = false;
async function mount(): Promise<void> {
  if (mounted) return;
  if (!document.body) return;
  // Skip mount in tiny iframes (analytics, ads, etc.)
  if (!IS_TOP) {
    const rect = document.documentElement.getBoundingClientRect();
    if (rect.width < 200 || rect.height < 200) return;
  }
  console.log(`${ORIGIN_TAG} mount`);

  const profile = await loadProfile();
  if (!profile) {
    if (IS_TOP) {
      mounted = true;
      mountOverlay(async () => ({ filled: 0, skipped: 0, byKey: {} }));
      const root = document.getElementById(OVERLAY_ID);
      if (root) {
        const note = root.querySelector("div") as HTMLDivElement | null;
        if (note) {
          note.style.display = "block";
          note.textContent =
            "Backend offline. Start the JobHunter dashboard (localhost:8000) to enable auto-fill.";
        }
      }
    }
    return;
  }
  // Only the top frame shows the overlay UI; iframes register a listener so
  // they can run autoFillForm() inside their own DOM on demand.
  if (!IS_TOP) {
    window.addEventListener("message", async (ev) => {
      if (ev.data?.__jobhunter_request !== "autofill") return;
      // Solo el frame padre directo, y solo desde un origen ATS de confianza.
      if (ev.source !== window.parent) return;
      if (!isTrustedFrameOrigin(ev.origin)) {
        console.warn(
          `${ORIGIN_TAG} ignored autofill request from untrusted origin: ${ev.origin}`,
        );
        return;
      }
      const result = await autoFillForm(profile);
      // Responde solo al origen que lo pidió, no a "*".
      (ev.source as Window).postMessage(
        { __jobhunter_response: "autofill", result, origin: location.host },
        ev.origin,
      );
    });
    console.log(`${ORIGIN_TAG} listener registered (iframe mode)`);
    mounted = true;
    return;
  }
  mounted = true;
  mountOverlay(async () => {
    const localResult = await autoFillForm(profile);
    // Also request iframes to fill themselves
    const iframes = Array.from(document.querySelectorAll("iframe"));
    const responses: AutoFillResult[] = [];
    for (const f of iframes) {
      try {
        const iframeResult = await new Promise<AutoFillResult | null>(
          (resolve) => {
            const timer = setTimeout(() => resolve(null), 1500);
            const handler = (ev: MessageEvent) => {
              // Solo acepta la respuesta del iframe concreto al que preguntamos.
              if (ev.source !== f.contentWindow) return;
              if (ev.data?.__jobhunter_response === "autofill") {
                clearTimeout(timer);
                window.removeEventListener("message", handler);
                resolve(ev.data.result as AutoFillResult);
              }
            };
            window.addEventListener("message", handler);
            try {
              f.contentWindow?.postMessage(
                { __jobhunter_request: "autofill" },
                "*",
              );
            } catch {
              clearTimeout(timer);
              window.removeEventListener("message", handler);
              resolve(null);
            }
          },
        );
        if (iframeResult) responses.push(iframeResult);
      } catch {
        /* ignore */
      }
    }
    // Merge results
    const merged: AutoFillResult = { ...localResult };
    for (const r of responses) {
      merged.filled += r.filled;
      merged.skipped += r.skipped;
      for (const [k, v] of Object.entries(r.byKey)) {
        merged.byKey[k] = (merged.byKey[k] ?? 0) + v;
      }
    }
    console.log(`${ORIGIN_TAG} autofill done`, merged);
    return merged;
  });
}

// First attempt as soon as the script runs
mount().catch(() => {});

// Re-mount on SPA navigation (Wellfound, etc.)
window.addEventListener("DOMContentLoaded", () => {
  mount().catch(() => {});
});

// Some SPAs (Wellfound, Lever) attach the modal to a portal far from body.
// Re-check periodically so the pill survives navigation that nukes our node.
setInterval(() => {
  if (!document.getElementById(OVERLAY_ID)) {
    mounted = false;
    mount().catch(() => {});
  }
}, 3000);
