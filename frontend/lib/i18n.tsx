"use client";

import * as React from "react";

export type Lang = "es" | "en";

type Entry = { es: string; en: string };

const DICT: Record<string, Entry> = {
  // stepper
  step_welcome: { es: "Bienvenida", en: "Welcome" },
  step_github: { es: "GitHub", en: "GitHub" },
  step_linkedin: { es: "LinkedIn", en: "LinkedIn" },
  step_cv: { es: "CV", en: "CV" },
  step_regions: { es: "Países", en: "Countries" },
  step_roles: { es: "Roles", en: "Roles" },
  step_ai: { es: "IA", en: "AI" },
  step_review: { es: "Revisión", en: "Review" },
  step_done: { es: "Listo", en: "Done" },
  // paso IA
  ai_title: { es: "¿Qué IA quieres usar?", en: "Which AI do you want to use?" },
  ai_desc: {
    es: "La IA analiza tu CV, puntúa ofertas y redacta materiales. Elige una; puedes cambiarla luego en Ajustes.",
    en: "AI analyzes your CV, scores jobs and drafts materials. Pick one; you can change it later in Settings.",
  },
  ai_local: { es: "Local · Ollama (gratis)", en: "Local · Ollama (free)" },
  ai_local_desc: {
    es: "Corre en tu máquina, sin coste ni clave. Recomendado.",
    en: "Runs on your machine, no cost or key. Recommended.",
  },
  ai_local_unavailable: {
    es: "Ollama no detectado (localhost:11434). Instálalo o elige otra opción.",
    en: "Ollama not detected (localhost:11434). Install it or pick another option.",
  },
  ai_cloud: { es: "Cloud · con tu API key", en: "Cloud · with your API key" },
  ai_cloud_desc: {
    es: "Anthropic / OpenAI / Gemini. Mejor calidad; de pago según tu uso.",
    en: "Anthropic / OpenAI / Gemini. Higher quality; paid per usage.",
  },
  ai_off: { es: "Sin IA (solo scraping)", en: "No AI (scraping only)" },
  ai_off_desc: {
    es: "Sin puntuación ni redacción IA. El análisis del CV será texto en bruto a revisar.",
    en: "No AI scoring or drafting. CV analysis will be raw text to review.",
  },
  ai_continue: { es: "Continuar", en: "Continue" },
  t_ai_saved: { es: "IA configurada", en: "AI configured" },
  t_ai_err: { es: "No se pudo guardar la IA", en: "Couldn't save AI settings" },
  // welcome
  welcome_title: { es: "Bienvenido a JobSlaves", en: "Welcome to JobSlaves" },
  welcome_desc: {
    es: "Todo corre en tu máquina (local-first, sin nube). Vamos a construir tu perfil a partir de tu GitHub, LinkedIn y CV. Nada se guarda sin que lo revises.",
    en: "Everything runs on your machine (local-first, no cloud). We'll build your profile from your GitHub, LinkedIn and CV. Nothing is saved without your review.",
  },
  start: { es: "Empezar", en: "Get started" },
  manual: { es: "Prefiero rellenarlo a mano", en: "I'd rather fill it in manually" },
  back: { es: "Atrás", en: "Back" },
  skip: { es: "Omitir", en: "Skip" },
  next: { es: "Siguiente", en: "Next" },
  imported: { es: "✓ importado", en: "✓ imported" },
  // github
  gh_title: { es: "Conecta tu GitHub", en: "Connect your GitHub" },
  gh_desc: {
    es: "Analizamos tus repos públicos para extraer skills y proyectos destacados. Opcional.",
    en: "We analyze your public repos to extract skills and highlight projects. Optional.",
  },
  gh_ph: { es: "usuario o https://github.com/usuario", en: "username or https://github.com/username" },
  import: { es: "Importar", en: "Import" },
  importing: { es: "Importando…", en: "Importing…" },
  // linkedin
  li_title: { es: "Importa tu LinkedIn", en: "Import your LinkedIn" },
  li_desc: {
    es: "Lo más rápido: pega el texto de tu perfil. O sube el export oficial (.zip) o el PDF. Sin riesgo de baneo.",
    en: "Fastest: paste your profile text. Or upload the official export (.zip) or PDF. No ban risk.",
  },
  li_paste_label: { es: "Pega el texto de tu perfil (rápido)", en: "Paste your profile text (fast)" },
  li_paste_ph: {
    es: "Copia tu 'Acerca de', experiencia y aptitudes desde tu perfil y pégalo aquí…",
    en: "Copy your 'About', experience and skills from your profile and paste here…",
  },
  li_paste_btn: { es: "Analizar texto", en: "Analyze text" },
  li_or_upload: { es: "O sube el export oficial (.zip) o PDF:", en: "Or upload the official export (.zip) or PDF:" },
  li_ext_note: {
    es: "¿Tienes la extensión? Ve a tu perfil de LinkedIn y pulsa «Importar a JobHunter» (lee solo tu propio perfil).",
    en: "Got the extension? Open your LinkedIn profile and click “Import to JobHunter” (reads only your own profile).",
  },
  // cv
  cv_title: { es: "Sube tu CV", en: "Upload your CV" },
  cv_desc: {
    es: "PDF, DOCX o TXT. Lo analizamos con IA para estructurar tu experiencia. Opcional.",
    en: "PDF, DOCX or TXT. We analyze it with AI to structure your experience. Optional.",
  },
  cv_drop: { es: "Arrastra tu CV (.pdf / .docx / .txt)", en: "Drop your CV (.pdf / .docx / .txt)" },
  processing: { es: "Procesando…", en: "Processing…" },
  // regions
  rg_title: { es: "¿Dónde quieres buscar trabajo?", en: "Where do you want to search?" },
  rg_desc: {
    es: "Activamos las plataformas relevantes a los países que elijas.",
    en: "We enable the platforms relevant to the countries you pick.",
  },
  rg_preset_es: { es: "Solo España", en: "Spain only" },
  rg_preset_eu: { es: "Toda Europa", en: "All Europe" },
  rg_preset_remote: { es: "Remoto (worldwide)", en: "Remote (worldwide)" },
  rg_or_countries: { es: "O elige países concretos:", en: "Or pick specific countries:" },
  // roles (paso IA)
  roles_title: { es: "¿Qué roles te interesan?", en: "Which roles interest you?" },
  roles_desc: {
    es: "La IA propone roles a partir de tu experiencia y skills. Afinan las búsquedas. Quita los que no encajen o añade los tuyos.",
    en: "AI suggests roles from your experience and skills. They tune the searches. Remove the ones that don't fit or add your own.",
  },
  roles_loading: { es: "Sugiriendo roles con IA…", en: "Suggesting roles with AI…" },
  roles_ai_note: { es: "Sugerido por IA", en: "AI suggested" },
  roles_empty: {
    es: "Sin sugerencias automáticas. Añade tus roles manualmente.",
    en: "No automatic suggestions. Add your roles manually.",
  },
  roles_add_ph: { es: "Añadir un rol propio…", en: "Add your own role…" },
  roles_add_btn: { es: "Añadir", en: "Add" },
  roles_selected: { es: "seleccionados", en: "selected" },
  generate: { es: "Generar perfil", en: "Generate profile" },
  // review
  rv_title: { es: "Revisa tu perfil", en: "Review your profile" },
  rv_desc: {
    es: "Lo generamos a partir de tus fuentes. Edita lo que quieras antes de guardar — nada se ha escrito todavía.",
    en: "Generated from your sources. Edit anything before saving — nothing has been written yet.",
  },
  rv_conflicts: { es: "dato(s) con discrepancias entre fuentes:", en: "field(s) with discrepancies between sources:" },
  rv_merging: { es: "Fusionando tu perfil…", en: "Merging your profile…" },
  rv_summary_es: { es: "Resumen (ES)", en: "Summary (ES)" },
  rv_exp: { es: "Experiencias", en: "Experiences" },
  rv_skills: { es: "Skills", en: "Skills" },
  rv_proj: { es: "Proyectos", en: "Projects" },
  rv_json: { es: "Editar JSON completo (avanzado)", en: "Edit full JSON (advanced)" },
  save: { es: "Guardar perfil", en: "Save profile" },
  saving: { es: "Guardando…", en: "Saving…" },
  f_name: { es: "Nombre", en: "Name" },
  f_title: { es: "Título profesional", en: "Professional title" },
  f_email: { es: "Email", en: "Email" },
  f_phone: { es: "Teléfono", en: "Phone" },
  f_location: { es: "Ubicación", en: "Location" },
  f_github: { es: "GitHub", en: "GitHub" },
  f_linkedin: { es: "LinkedIn", en: "LinkedIn" },
  f_portfolio: { es: "Portfolio", en: "Portfolio" },
  c_ES: { es: "España", en: "Spain" },
  c_DE: { es: "Alemania", en: "Germany" },
  c_FR: { es: "Francia", en: "France" },
  c_SE: { es: "Suecia", en: "Sweden" },
  c_GB: { es: "Reino Unido", en: "United Kingdom" },
  c_NL: { es: "Países Bajos", en: "Netherlands" },
  c_IT: { es: "Italia", en: "Italy" },
  c_PT: { es: "Portugal", en: "Portugal" },
  c_REMOTE: { es: "Remoto", en: "Remote" },
  done_title: { es: "¡Perfil creado! 🎉", en: "Profile created! 🎉" },
  done_desc: {
    es: "Tu cv_master.json ya está listo. Puedes ajustarlo cuando quieras en Ajustes.",
    en: "Your cv_master.json is ready. You can tweak it anytime in Settings.",
  },
  go_dashboard: { es: "Ir al dashboard", en: "Go to dashboard" },
  t_gh_ok: { es: "GitHub importado", en: "GitHub imported" },
  t_gh_err: { es: "No se pudo importar GitHub (¿usuario correcto?)", en: "Couldn't import GitHub (correct username?)" },
  t_file_err: { es: "No se pudo procesar el archivo", en: "Couldn't process the file" },
  t_li_ok: { es: "LinkedIn importado", en: "LinkedIn imported" },
  t_cv_ok: { es: "CV analizado", en: "CV analyzed" },
  t_text_empty: { es: "Pega algo de texto primero", en: "Paste some text first" },
  t_name_req: { es: "El nombre es obligatorio", en: "Name is required" },
  t_region_req: { es: "Elige al menos una región o país", en: "Pick at least one region or country" },
  t_saved_err: { es: "No se pudo guardar el perfil", en: "Couldn't save the profile" },
  t_json_ok: { es: "JSON aplicado", en: "JSON applied" },
  t_json_err: { es: "JSON inválido, no aplicado", en: "Invalid JSON, not applied" },
};

interface I18nCtx {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string) => string;
}

const Ctx = React.createContext<I18nCtx>({ lang: "es", setLang: () => {}, t: (k) => k });

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = React.useState<Lang>("es");

  React.useEffect(() => {
    try {
      const saved = localStorage.getItem("jh_lang") as Lang | null;
      if (saved === "es" || saved === "en") setLangState(saved);
    } catch {
      /* ignore */
    }
  }, []);

  const setLang = React.useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("jh_lang", l);
    } catch {
      /* ignore */
    }
  }, []);

  const t = React.useCallback((key: string) => DICT[key]?.[lang] ?? key, [lang]);

  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>;
}

export function useLang(): I18nCtx {
  return React.useContext(Ctx);
}

export function LanguageToggle() {
  const { lang, setLang } = useLang();
  return (
    <div className="inline-flex overflow-hidden rounded-full border border-[hsl(var(--border))] text-xs">
      {(["es", "en"] as Lang[]).map((l) => (
        <button
          key={l}
          onClick={() => setLang(l)}
          className={
            "px-2.5 py-1 uppercase transition-colors " +
            (lang === l
              ? "bg-[hsl(var(--accent-1))]/20 text-[hsl(var(--accent-1))]"
              : "text-muted-foreground hover:text-foreground")
          }
        >
          {l}
        </button>
      ))}
    </div>
  );
}
