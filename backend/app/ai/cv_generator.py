"""Generador de CV adaptado en formato Typst, compilado a PDF.

Internamente usa el LLMRouter (tier=generation) con fallback automatico.
Mantiene la firma publica `generate_cv(cv_master, job, out_dir, language=None)`.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.ai.client import run_sync
from app.ai.router import get_router
from app.config import settings

logger = logging.getLogger(__name__)

CV_SYSTEM = """Eres un experto en adaptar CVs tecnicos al puesto exacto.

Recibes:
- cv_master: JSON con datos completos del candidato.
- cv_template: codigo Typst de plantilla con marcadores.
- job: titulo, empresa, descripcion.

Tu tarea: devolver UN UNICO documento Typst (.typ) listo para compilar.

REGLAS:
- Mantener la estructura visual de la plantilla.
- Reordenar projects y skills segun lo que pide la oferta (lo mas relevante primero).
- Reescribir el summary (3-4 lineas) para alinearlo con la oferta.
- Maximo 1-1.5 paginas.
- No inventar experiencia, titulos ni stack. Usar solo datos del cv_master.
- Idioma del CV: castellano si la oferta esta en castellano; si esta en ingles, ingles.
- Devolver UNICAMENTE el contenido Typst, sin markdown fences, sin comentarios extra."""


def _detect_language(text: str) -> str:
    text_l = text.lower()
    es_markers = ["desarrollador", "ingeniero", "responsable", "habilidades", "experiencia", "se valora"]
    en_markers = ["developer", "engineer", "responsibilities", "requirements", "we offer"]
    es = sum(1 for m in es_markers if m in text_l)
    en = sum(1 for m in en_markers if m in text_l)
    return "es" if es >= en else "en"


def _ensure_typst() -> bool:
    return shutil.which("typst") is not None


class CVGenerationError(RuntimeError):
    """Raised when the CV PDF could not be produced.

    Distinguishes 'typst not installed' / 'typst compile failed' / 'no PDF
    written' from other errors so the API layer can return an actionable
    HTTP error to the user instead of storing a phantom cv_path that later
    breaks the download endpoint with 'file missing on disk'.
    """


# Typst interprets `@key` as a bibliography reference. Emails like
# `foo@example.com` blow up the compile with:
#   error: label `<example.com>` does not exist in the document
# Escape every `@` that looks like an email so it renders as literal text.
_EMAIL_RX = re.compile(r"(?<!\\)([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")


def _escape_typst_emails(source: str) -> str:
    """Replace `foo@bar.com` with `foo\\@bar.com` so Typst treats it as text."""
    return _EMAIL_RX.sub(r"\1\\@\2", source)


def _basic_typst_from_master(cv: dict[str, Any], template: str) -> str:
    """Fallback sin LLM: rellena la plantilla con datos brutos."""
    p = cv.get("personal", {})
    summary = cv.get("summary", "")
    skills = cv.get("skills", {})
    exp = cv.get("experience", [])
    proj = cv.get("projects", [])
    edu = cv.get("education", [])

    exp_block = "\n".join(
        f"=== {e.get('role', '')} -- {e.get('company', '')} ({e.get('start', '')}--{e.get('end') or 'present'})\n"
        + "\n".join(f"- {h}" for h in e.get("highlights", []))
        for e in exp
    )
    proj_block = "\n".join(
        f"=== {pr.get('name', '')} -- {', '.join(pr.get('stack', []))}\n{pr.get('description', '')}"
        for pr in proj[:5]
    )
    skills_block = "\n".join(f"- *{k}*: {', '.join(v)}" for k, v in skills.items() if isinstance(v, list))
    edu_block = "\n".join(
        f"- *{e.get('degree', '')}* -- {e.get('school', '')} ({e.get('year', '')})" for e in edu
    )

    out = template
    replacements = {
        "{{NAME}}": p.get("name", ""),
        "{{TITLE}}": p.get("title", ""),
        "{{EMAIL}}": p.get("email", ""),
        "{{PHONE}}": p.get("phone", ""),
        "{{LOCATION}}": p.get("location", ""),
        "{{GITHUB}}": p.get("github", ""),
        "{{LINKEDIN}}": p.get("linkedin", ""),
        "{{PORTFOLIO}}": p.get("portfolio", ""),
        "{{SUMMARY}}": summary,
        "{{EXPERIENCE}}": exp_block,
        "{{PROJECTS}}": proj_block,
        "{{SKILLS}}": skills_block,
        "{{EDUCATION}}": edu_block,
    }
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out


def _build_user_prompt(cv_master: dict[str, Any], template: str, job: dict[str, Any], lang: str) -> str:
    return (
        "cv_master:\n" + json.dumps(cv_master, ensure_ascii=False)
        + "\n\ncv_template:\n" + template
        + f"\n\nOferta (idioma={lang}):\n"
        + json.dumps(
            {
                "title": job.get("title"),
                "company": job.get("company"),
                "description": (job.get("description") or "")[:5000],
            },
            ensure_ascii=False,
        )
    )


def generate_cv(
    cv_master: dict[str, Any],
    job: dict[str, Any],
    out_dir: Path,
    language: str | None = None,
) -> tuple[Path, str, str]:
    """Genera CV personalizado para la oferta.

    Returns:
        (pdf_path, typst_source, language)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    template_path = settings.cv_template_file
    template = template_path.read_text(encoding="utf-8") if template_path.exists() else ""

    lang = language or _detect_language(job.get("description", "") or job.get("title", ""))

    typst_source: str
    router = get_router()
    has_provider = bool(router.available_providers("generation"))

    if not has_provider or not template:
        typst_source = _basic_typst_from_master(cv_master, template or _MINIMAL_TEMPLATE)
    else:
        try:
            user_prompt = _build_user_prompt(cv_master, template, job, lang)
            response = run_sync(
                router.complete_for(
                    tier="generation",
                    system=CV_SYSTEM,
                    user=user_prompt,
                    max_tokens=4000,
                    temperature=0.3,
                )
            )
            typst_source = response.content.strip()
            if typst_source.startswith("```"):
                typst_source = typst_source.strip("`")
                if typst_source.lower().startswith("typst"):
                    typst_source = typst_source[5:].lstrip("\n")
        except Exception as exc:  # noqa: BLE001
            logger.exception("CV gen via router fallido, usando basico: %s", exc)
            typst_source = _basic_typst_from_master(cv_master, template or _MINIMAL_TEMPLATE)

    # Guarantee no `foo@bar.com` sneaks in unescaped (Typst would treat @bar.com
    # as a bibliography reference and abort compile).
    typst_source = _escape_typst_emails(typst_source)

    typst_file = out_dir / "cv.typ"
    typst_file.write_text(typst_source, encoding="utf-8")
    pdf_file = out_dir / "cv.pdf"

    if not _ensure_typst():
        raise CVGenerationError(
            "typst binary not found in PATH. Install it and retry:\n"
            "  macOS:   brew install typst\n"
            "  Linux:   cargo install --locked typst-cli  (or download from github.com/typst/typst/releases)\n"
            "  Windows: winget install typst  (or scoop install typst)\n"
            "  Docker:  the bundled image already has it — use `docker compose up`\n"
            "Without typst the CV cannot be compiled to PDF."
        )

    try:
        subprocess.run(
            ["typst", "compile", str(typst_file), str(pdf_file)],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="ignore") if exc.stderr else ""
        logger.error("Typst compile failed for %s: %s", typst_file, stderr[:500])
        raise CVGenerationError(
            f"Typst compile failed. Source saved at {typst_file} for debugging.\n"
            f"typst stderr:\n{stderr[:800]}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise CVGenerationError(
            f"Typst compile timed out (60s). Source at {typst_file}."
        ) from exc

    if not pdf_file.exists():
        raise CVGenerationError(
            f"Typst compile reported success but {pdf_file} is missing. "
            "This is a bug — please report it."
        )

    return pdf_file, typst_source, lang


_MINIMAL_TEMPLATE = r"""
#set page(margin: 1.5cm, paper: "a4")
#set text(font: "Inter", size: 10pt)

#align(center)[
  #text(size: 18pt, weight: "bold")[{{NAME}}] \\
  #text(size: 11pt)[{{TITLE}}] \\
  {{EMAIL}} -- {{PHONE}} -- {{LOCATION}} \\
  #link("{{GITHUB}}") -- #link("{{LINKEDIN}}") -- #link("{{PORTFOLIO}}")
]

== Summary
{{SUMMARY}}

== Experience
{{EXPERIENCE}}

== Projects
{{PROJECTS}}

== Skills
{{SKILLS}}

== Education
{{EDUCATION}}
"""
