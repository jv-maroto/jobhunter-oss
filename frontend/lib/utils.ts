import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { format, formatDistanceToNow, parseISO } from "date-fns";
import { es } from "date-fns/locale";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

function safeParse(dateStr?: string | null): Date | null {
  if (!dateStr) return null;
  try {
    const d = parseISO(dateStr);
    return isNaN(d.getTime()) ? null : d;
  } catch {
    return null;
  }
}

export function apiDate(value?: string | null): Date | null {
  if (!value) return null;
  const normalized = /T/.test(value) && !/(Z|[+-]\d{2}:?\d{2})$/i.test(value) ? `${value}Z` : value;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function localDateTimeInput(value?: string | null): string {
  const date = apiDate(value);
  if (!date) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function publicJobUrl(value?: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export function formatRelative(dateStr?: string | null, fallback = "—"): string {
  const d = safeParse(dateStr);
  if (!d) return fallback;
  return formatDistanceToNow(d, { addSuffix: true, locale: es });
}

export function formatShort(dateStr?: string | null, fmt = "EEE d MMM", fallback = "—"): string {
  const d = safeParse(dateStr);
  if (!d) return fallback;
  return format(d, fmt, { locale: es });
}

export function formatSalary(
  min?: number | null,
  max?: number | null,
  currency?: string | null,
  period?: string | null,
): string {
  const valid = (n: number | null | undefined): n is number => typeof n === "number" && Number.isFinite(n) && n >= 0;
  if (!valid(min) && !valid(max)) return "—";
  const amount = (n: number) => n >= 1000 ? `${Number((n / 1000).toFixed(2))}k` : String(n);
  const range = valid(min) && valid(max)
    ? (min === max ? amount(min) : `${amount(min)}–${amount(max)}`)
    : valid(min) ? `${amount(min)}+` : `≤${amount(max!)}`;
  const code = currency?.trim().toUpperCase();
  const unit = code === "EUR" ? "€" : code === "GBP" ? "£" : code || "currency unknown";
  return `${range} ${unit}${period ? ` / ${period}` : ""}`;
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

/**
 * Maps a 0-100 score to a coherent visual token tuple used across
 * badges, charts and rings. Higher = good (green), low = warn (rose).
 */
export function scoreTone(score: number): {
  color: string;             // raw CSS color (hsl var)
  bg: string;                // tailwind classes for solid bg
  text: string;              // tailwind classes for text
  ring: string;              // border ring tailwind classes
  label: string;
} {
  if (score >= 90)
    return {
      color: "hsl(var(--score-good))",
      bg: "bg-[hsl(var(--score-good))]/15",
      text: "text-[hsl(var(--score-good))]",
      ring: "ring-1 ring-[hsl(var(--score-good))]/35",
      label: "Excellent",
    };
  if (score >= 70)
    return {
      color: "hsl(var(--score-good))",
      bg: "bg-[hsl(var(--score-good))]/12",
      text: "text-[hsl(var(--score-good))]",
      ring: "ring-1 ring-[hsl(var(--score-good))]/25",
      label: "Strong",
    };
  if (score >= 50)
    return {
      color: "hsl(var(--score-mid))",
      bg: "bg-[hsl(var(--score-mid))]/12",
      text: "text-[hsl(var(--score-mid))]",
      ring: "ring-1 ring-[hsl(var(--score-mid))]/30",
      label: "Maybe",
    };
  return {
    color: "hsl(var(--score-bad))",
    bg: "bg-[hsl(var(--score-bad))]/12",
    text: "text-[hsl(var(--score-bad))]",
    ring: "ring-1 ring-[hsl(var(--score-bad))]/30",
    label: "Skip",
  };
}

/** DiceBear pixel-art avatar URL for a given seed. */
export function avatarFor(seed: string, size = 40): string {
  const safe = encodeURIComponent(seed.trim() || "anon");
  return `https://api.dicebear.com/9.x/thumbs/svg?seed=${safe}&size=${size}&radius=12`;
}

/** Format euros like "€2.41" / "€0.00". */
export function formatEur(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "€0.00";
  return `€${v.toFixed(2)}`;
}

/**
 * Heuristic language detection (es / en / pt / fr / other).
 * Counts language-specific tokens; cheap, no dependency.
 */
export function detectLanguage(
  ...texts: (string | null | undefined)[]
): "es" | "en" | "pt" | "fr" | "other" {
  const t = texts.filter(Boolean).join(" ").toLowerCase();
  if (!t || t.length < 20) return "other";
  const en = (t.match(/\b(the|and|with|you|our|are|we're|looking|experience|we'?ll|skills|teams?)\b/g) || []).length;
  const es = (t.match(/\b(que|para|con|los|las|una|estamos|buscamos|experiencia|puesto|trabajar|nuestra|nuestro|empresa)\b/g) || []).length;
  const pt = (t.match(/\b(você|estamos|para o|com a|nossa|nosso|equipa|experiência|procuramos)\b/g) || []).length;
  const fr = (t.match(/\b(nous|vous|notre|votre|recherche|expérience|équipe|entreprise|chez)\b/g) || []).length;
  const counts: Array<["en" | "es" | "pt" | "fr", number]> = [
    ["en", en], ["es", es], ["pt", pt], ["fr", fr],
  ];
  counts.sort((a, b) => b[1] - a[1]);
  if (counts[0][1] < 2) return "other";
  return counts[0][0];
}

/** Display label + flag for a detected language. */
export function languageLabel(lang: string): { label: string; flag: string } {
  switch (lang) {
    case "es": return { label: "ES", flag: "🇪🇸" };
    case "en": return { label: "EN", flag: "🇬🇧" };
    case "pt": return { label: "PT", flag: "🇵🇹" };
    case "fr": return { label: "FR", flag: "🇫🇷" };
    default:   return { label: "—",  flag: "" };
  }
}

export type ApplyFriction = "easy" | "medium" | "hard";

export function sourceFriction(source?: string | null): {
  level: ApplyFriction;
  label: string;
  hint: string;
} {
  return {
    level: "medium",
    label: source === "manual" ? "Saved posting" : "Check posting",
    hint: "Review the employer's posting for its application steps. Opening a link does not submit an application.",
  };
}

/** Numeric score for friction so we can sort or weight match. */
export function frictionPenalty(source?: string | null): number {
  const { level } = sourceFriction(source);
  if (level === "easy") return 0;
  if (level === "medium") return 5;
  return 15;
}
