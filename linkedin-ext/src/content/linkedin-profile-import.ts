/**
 * Importar tu propio perfil de LinkedIn al onboarding (alternativa rápida al ZIP).
 *
 * Solo corre en paginas de perfil (/in/*). Lee de TU sesion los campos basicos
 * (nombre, titular, "Acerca de", skills) y los manda al backend
 * (POST /onboarding/linkedin/from-extension). No scrapea perfiles ajenos en masa:
 * es tu propio perfil, en tu navegador. Tu revisas todo en el wizard.
 */
import { api } from "../lib/api";

const BTN_ID = "jobhunter-li-import";

function txt(sel: string): string {
  const el = document.querySelector(sel);
  return (el?.textContent || "").trim();
}

function scrapeProfile() {
  const name = txt("h1");
  const headline = txt(".text-body-medium.break-words") || txt(".pv-text-details__left-panel .text-body-medium");

  // "Acerca de": la seccion con anchor #about, tomamos el span de texto visible.
  let summary = "";
  const about = document.querySelector("#about");
  if (about) {
    const section = about.closest("section");
    const span = section?.querySelector(".inline-show-more-text span[aria-hidden='true'], .display-flex span[aria-hidden='true']");
    summary = (span?.textContent || section?.textContent || "").trim().slice(0, 4000);
  }

  // Skills: spans dentro de la seccion #skills.
  const skills: string[] = [];
  const skillsAnchor = document.querySelector("#skills");
  const skillsSection = skillsAnchor?.closest("section");
  skillsSection?.querySelectorAll("a[data-field='skill_card_skill_topic'] span[aria-hidden='true'], .mr1 span[aria-hidden='true']").forEach((n) => {
    const s = (n.textContent || "").trim();
    if (s && s.length < 60 && !skills.includes(s)) skills.push(s);
  });

  return {
    name,
    headline,
    summary,
    profile_url: location.href.split("?")[0],
    skills: skills.slice(0, 30)
  };
}

function buildButton(): void {
  if (document.getElementById(BTN_ID)) return;
  const btn = document.createElement("button");
  btn.id = BTN_ID;
  btn.textContent = "⬇ Importar a JobHunter";
  btn.style.cssText = [
    "position:fixed", "bottom:20px", "right:20px", "z-index:2147483647",
    "background:#0b0f17", "color:#58a6ff", "border:1px solid #1f6feb55",
    "border-radius:10px", "padding:10px 14px", "cursor:pointer",
    "font:600 13px system-ui,sans-serif", "box-shadow:0 8px 30px rgba(0,0,0,.5)"
  ].join(";");
  btn.onclick = async () => {
    btn.disabled = true;
    btn.textContent = "Importando…";
    try {
      const payload = scrapeProfile();
      if (!payload.name) throw new Error("sin nombre");
      await api.importLinkedinProfile(payload);
      btn.textContent = "✓ Importado — vuelve al wizard";
      btn.style.color = "#3fb950";
      btn.style.borderColor = "#23863655";
    } catch {
      btn.disabled = false;
      btn.textContent = "Error (¿backend_url en opciones?)";
    }
  };
  document.body.appendChild(btn);
}

if (location.pathname.startsWith("/in/")) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", buildButton);
  } else {
    buildButton();
  }
}
