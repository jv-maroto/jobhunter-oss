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
  min?: number,
  max?: number,
  currency = "EUR",
): string {
  const symbol = currency === "EUR" ? "€" : currency === "USD" ? "$" : currency;
  if (!min && !max) return "—";
  if (min && max) return `${min / 1000}k–${max / 1000}k ${symbol}`;
  const v = (min ?? max)!;
  return `${v / 1000}k ${symbol}`;
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

/**
 * How much friction it takes to actually apply to a job from each source.
 * Used to weight the Today table — easy sources first, hard sources last.
 */
export type ApplyFriction = "easy" | "medium" | "hard";

export function sourceFriction(source?: string | null): {
  level: ApplyFriction;
  label: string;
  hint: string;
} {
  const s = (source ?? "").toLowerCase();
  if (
    s.includes("linkedin") ||
    s.includes("welcometothejungle") ||
    s.includes("welcome") ||
    s.includes("otta") ||
    s.includes("landing.jobs") ||
    s.includes("workable")
  ) {
    return {
      level: "easy",
      label: "Easy apply",
      hint: "1-2 clicks with your saved profile. Apply from this list directly.",
    };
  }
  if (s.includes("wellfound") || s.includes("angellist")) {
    return {
      level: "medium",
      label: "Account",
      hint: "Wellfound (AngelList Talent): one-time account import from LinkedIn, then 2-click apply.",
    };
  }
  if (s.includes("remotive")) {
    return {
      level: "medium",
      label: "External link",
      hint: "Remotive aggregates jobs from external sites — you'll land on the company ATS.",
    };
  }
  if (
    s.includes("indeed") ||
    s.includes("glassdoor") ||
    s.includes("ziprecruiter") ||
    s.includes("monster")
  ) {
    return {
      level: "hard",
      label: "Account first",
      hint: "Indeed/Glassdoor/ZipRecruiter ask to create an account or redirect to external site. Do that ONCE then it gets easier.",
    };
  }
  return {
    level: "medium",
    label: "Form",
    hint: "Custom form. Use the generated CV + cover, fill in 1-2 fields by hand.",
  };
}

/** Numeric score for friction so we can sort or weight match. */
export function frictionPenalty(source?: string | null): number {
  const { level } = sourceFriction(source);
  if (level === "easy") return 0;
  if (level === "medium") return 5;
  return 15;
}
