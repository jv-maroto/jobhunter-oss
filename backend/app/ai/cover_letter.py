"""Generador de carta de presentacion personalizada.

Internamente usa el LLMRouter (tier=generation) con fallback automatico.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.ai.client import run_sync
from app.ai.router import get_router

logger = logging.getLogger(__name__)

COVER_SYSTEM = """Eres un experto en redactar cartas de presentacion concisas y personalizadas.

REGLAS:
- 200-300 palabras maximo.
- Tono profesional pero humano, sin formalismos vacios.
- Estructura: hook (que te interesa de la empresa) -> por que encajas (1-2 proyectos del usuario que sean relevantes a la oferta) -> closing con CTA.
- Mencionar 2-3 personalization_hooks proporcionados.
- Idioma EXACTO segun el campo `language`.
- Devolver UNICAMENTE el cuerpo de la carta en texto plano, sin markdown, sin saludo formal repetido,
  sin firma (la firma se anade aparte)."""


def _fallback_cover(cv: dict[str, Any], job: dict[str, Any], language: str) -> str:
    personal = cv.get("personal", {})
    name = personal.get("name", "")
    company = job.get("company", "")
    title = job.get("title", "")
    proj = cv.get("projects", [])
    p1 = proj[0]["name"] if proj else "personal projects"
    p2 = proj[1]["name"] if len(proj) > 1 else "production deployments"

    if language == "es":
        return (
            f"Me dirijo a {company} con interes en la posicion de {title}.\n\n"
            f"Soy {name}, ingeniero Full-Stack Python con experiencia construyendo aplicaciones reales "
            f"de extremo a extremo. Recientemente he desarrollado {p1} y {p2}, lo que me ha permitido "
            "trabajar con FastAPI, React 19, PostgreSQL y Docker en produccion. Mi background en "
            "administracion de sistemas Linux/Windows me da una perspectiva valiosa sobre fiabilidad y "
            "despliegue, no solo sobre el codigo.\n\n"
            "Me interesa especialmente el enfoque tecnico de vuestro equipo y la posibilidad de aportar "
            "calidad desde el primer dia. Estoy disponible para una conversacion cuando os venga bien."
        )
    return (
        f"I'm writing regarding the {title} position at {company}.\n\n"
        f"My name is {name}, a Full-Stack Python + AI engineer with hands-on experience shipping production "
        f"applications. Recent projects include {p1} and {p2}, where I worked with FastAPI, React 19, "
        "PostgreSQL and Docker end-to-end. My sysadmin background (Linux, Windows Server, CIS hardening) "
        "gives me a reliability-first mindset that complements pure dev work.\n\n"
        "I'd love to learn more about the team's roadmap and discuss how I can contribute. Looking forward "
        "to hearing from you."
    )


def _build_user_prompt(
    cv_master: dict[str, Any],
    job: dict[str, Any],
    hooks: list[str],
    language: str,
) -> str:
    return (
        "cv_master:\n" + json.dumps(cv_master, ensure_ascii=False)
        + f"\nlanguage={language}"
        + "\nhooks=" + json.dumps(hooks, ensure_ascii=False)
        + "\noferta=" + json.dumps(
            {
                "title": job.get("title"),
                "company": job.get("company"),
                "location": job.get("location"),
                "description": (job.get("description") or "")[:4000],
            },
            ensure_ascii=False,
        )
    )


def generate_cover_letter(
    cv_master: dict[str, Any],
    job: dict[str, Any],
    personalization_hooks: list[str],
    out_dir: Path,
    language: str = "en",
) -> tuple[Path, str]:
    """Genera carta de presentacion en texto plano y PDF.

    Returns (pdf_path, content).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    router = get_router()
    has_provider = bool(router.available_providers("generation"))

    content: str
    if not has_provider:
        content = _fallback_cover(cv_master, job, language)
    else:
        try:
            user_prompt = _build_user_prompt(cv_master, job, personalization_hooks, language)
            response = run_sync(
                router.complete_for(
                    tier="generation",
                    system=COVER_SYSTEM,
                    user=user_prompt,
                    max_tokens=1200,
                    temperature=0.4,
                )
            )
            content = response.content.strip()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Cover via router fallido: %s", exc)
            content = _fallback_cover(cv_master, job, language)

    txt_path = out_dir / "cover.txt"
    txt_path.write_text(content, encoding="utf-8")

    pdf_path = out_dir / "cover.pdf"
    _compile_cover_pdf(content, cv_master, job, out_dir, pdf_path)

    return pdf_path, content


def _compile_cover_pdf(
    content: str,
    cv: dict[str, Any],
    job: dict[str, Any],
    out_dir: Path,
    pdf_path: Path,
) -> None:
    """Compile the cover letter to PDF. Raises CVGenerationError if typst is
    missing or compile fails — so the caller can surface a real error instead
    of persisting a phantom cover_letter_path that later 410s."""
    from app.ai.cv_generator import CVGenerationError
    if shutil.which("typst") is None:
        raise CVGenerationError(
            "typst binary not found in PATH. Install it and retry:\n"
            "  macOS:   brew install typst\n"
            "  Linux:   cargo install --locked typst-cli  (or download from github.com/typst/typst/releases)\n"
            "  Windows: winget install typst  (or scoop install typst)\n"
            "  Docker:  the bundled image already has it — use `docker compose up`\n"
            "Cover letter PDF was not generated (the .typ source is still saved)."
        )
    p = cv.get("personal", {})
    typst = f"""#set page(margin: 2cm, paper: \"a4\")
#set text(font: \"Inter\", size: 11pt)
#align(right)[
  #text(weight: \"bold\")[{p.get('name', '')}] \\
  {p.get('email', '')} -- {p.get('phone', '')}
]
#v(1em)
{job.get('company', '')} \\
#v(0.5em)
"""
    typst += "\n\n".join(content.split("\n\n"))
    typst += f"\n#v(2em)\nAtentamente, \\\n{p.get('name', '')}\n"

    # Escape @ in emails so Typst doesn't parse them as bib references.
    from app.ai.cv_generator import _escape_typst_emails
    typst = _escape_typst_emails(typst)

    typ_file = out_dir / "cover.typ"
    typ_file.write_text(typst, encoding="utf-8")
    try:
        subprocess.run(
            ["typst", "compile", str(typ_file), str(pdf_path)],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="ignore") if exc.stderr else ""
        logger.error("typst cover compile failed for %s: %s", typ_file, stderr[:500])
        raise CVGenerationError(
            f"Typst compile of cover letter failed. Source saved at {typ_file}.\n"
            f"typst stderr:\n{stderr[:800]}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise CVGenerationError(
            f"Typst compile of cover letter timed out (60s). Source at {typ_file}."
        ) from exc

    if not pdf_path.exists():
        raise CVGenerationError(
            f"Typst reported success but {pdf_path} is missing. Please report this bug."
        )
