"""Generador de imagenes V5 — estilo infografía técnica completa.

Inspirado en las cards que produce ChatGPT con Code Interpreter: contiene
hero + code panel + "¿Cómo funciona?" con steps + mockup Telegram + bullets
+ servicios al pie + closer line. Todo en una sola imagen.

Tamaño: 1200x900 (formato vertical, mejor para LinkedIn feed engagement).
Render con Playwright headless. Fonts via Google Fonts CDN.
"""

from __future__ import annotations

import base64
import logging
import re
import shutil
import subprocess
import textwrap
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Any

from app.ai import profile_context
from app.config import settings

logger = logging.getLogger(__name__)


WIDTH = 1200
HEIGHT = 900

PEEPO_DIR = Path(__file__).parent / "assets" / "peepos"


def _author_info() -> dict[str, str]:
    """Reads name/title/portfolio from cv_master.json so generated images
    are personalized to whoever runs this instance. Falls back to placeholders."""
    try:
        from app.services import load_cv_master
        cv = load_cv_master() or {}
        personal = cv.get("personal") or {}
        name = (personal.get("name") or "").strip() or "Your Name"
        # Initials: first letter of first 2 name parts
        parts = [p for p in name.split() if p]
        initials = "".join(p[0] for p in parts[:2]).upper() or "?"
        title = (
            (personal.get("title") or "").strip()
            or cv.get("positioning")
            or "Full-Stack Engineer"
        )
        portfolio = (personal.get("portfolio") or "").strip()
        if portfolio.startswith("http"):
            portfolio_display = re.sub(r"^https?://(www\.)?", "", portfolio).rstrip("/")
        else:
            portfolio_display = portfolio or ""
        return {
            "name": name,
            "initials": initials,
            "title": title,
            "portfolio": portfolio_display,
        }
    except Exception:  # noqa: BLE001
        return {"name": "Your Name", "initials": "YN", "title": "Engineer", "portfolio": ""}


@lru_cache(maxsize=8)
def _peepo_data_uri(name: str) -> str:
    """Read a peepo (webp/gif/png) and return a data: URI. Empty string if missing."""
    for ext, mime in (("gif", "image/gif"), ("webp", "image/webp"), ("png", "image/png")):
        path = PEEPO_DIR / f"{name}.{ext}"
        if path.exists():
            raw = path.read_bytes()
            return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
    return ""


PEEPO_HERO_BY_CAT: dict[str, str] = {
    "sysadmin": "Nerdge",       # debugging mode
    "python":   "peepoHappy",
    "ai":       "owonerd",      # AI nerd
    "frontend": "OWO",
    "project":  "PepePls",
    "career":   "OkayGe",
}
PEEPO_CLOSER_BY_CAT: dict[str, str] = {
    "sysadmin": "OkayGe",       # back to green
    "python":   "Nerdge",
    "ai":       "OkayGe",
    "frontend": "peepoHappy",
    "project":  "peepoHappy",
    "career":   "peepoPls",
}


# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------

CATEGORY_DEFS: dict[str, dict[str, Any]] = {
    "python": {
        "tag": "PYTHON · BACKEND",
        "accent": "#3b82f6",
        "accent_soft": "rgba(59, 130, 246, 0.15)",
        "tab": "main.py",
        "lang": "python",
    },
    "ai": {
        "tag": "AI · LLM LOCAL",
        "accent": "#a855f7",
        "accent_soft": "rgba(168, 85, 247, 0.15)",
        "tab": "agent.py",
        "lang": "python",
    },
    "sysadmin": {
        "tag": "SYSADMIN · DEVOPS",
        "accent": "#10b981",
        "accent_soft": "rgba(16, 185, 129, 0.15)",
        "tab": "healthcheck.sh",
        "lang": "bash",
    },
    "frontend": {
        "tag": "FRONTEND · REACT",
        "accent": "#f59e0b",
        "accent_soft": "rgba(245, 158, 11, 0.15)",
        "tab": "App.tsx",
        "lang": "tsx",
    },
    "project": {
        "tag": "PROJECT",
        "accent": "#22d3ee",
        "accent_soft": "rgba(34, 211, 238, 0.15)",
        "tab": "README.md",
        "lang": "text",
    },
    "career": {
        "tag": "CAREER",
        "accent": "#a3e635",
        "accent_soft": "rgba(163, 230, 53, 0.15)",
        "tab": "story.md",
        "lang": "text",
    },
}


def _detect_category(content: str, category: str | None = None) -> str:
    if category and category.lower() in CATEGORY_DEFS:
        return category.lower()
    text = content.lower()
    if any(k in text for k in ["ollama", "llm", "claude", "gpt", "whisper", "yolo", "embeddings", "pgvector"]):
        return "ai"
    if any(k in text for k in ["bash", "ssh", "active directory", "windows server", "rsync", "ldap", "cron", "systemd", "docker ps", "rdp"]):
        return "sysadmin"
    if any(k in text for k in ["react", "tailwind", "vite", "tsx", "next.js"]):
        return "frontend"
    if any(k in text for k in ["fastapi", "django", "celery", "pydantic", "sqlalchemy"]):
        return "python"
    projects = profile_context.project_keywords()
    if projects and any(k in text for k in projects):
        return "project"
    if any(k in text for k in ["entrevista", "carrera", "transición", "aprendí", "lección"]):
        return "career"
    return "project"


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------


def _detect_code(content: str) -> str | None:
    m = re.search(r"```(?:[a-zA-Z+]*)\n(.+?)```", content, re.DOTALL)
    if not m:
        return None
    lines = m.group(1).strip().split("\n")
    return "\n".join(lines[:12])


def _hook(content: str) -> str:
    """First sentence — used as subtitle under the title."""
    cleaned = re.sub(r"```.+?```", "", content, flags=re.DOTALL).strip()
    first = cleaned.split("\n\n")[0]
    sentences = re.split(r"(?<=[.!?])\s+", first)
    s = (sentences[0] if sentences else cleaned[:200]).strip()
    if len(s) > 130:
        s = s[:130].rsplit(" ", 1)[0] + "…"
    return s


def _bullets(content: str, max_n: int = 3, max_len: int = 110) -> list[str]:
    cleaned = re.sub(r"```.+?```", "", content, flags=re.DOTALL)
    out: list[str] = []
    for raw in cleaned.split("\n"):
        line = raw.strip().lstrip("-*•  \t")
        line = re.sub(r"^\s*\d+[.)\-]\s*", "", line).strip()
        if 25 <= len(line) <= max_len and not line.endswith(":"):
            out.append(line)
        if len(out) >= max_n:
            break
    if len(out) < max_n:
        first = cleaned.strip().split("\n\n")[0]
        for s in re.split(r"(?<=[.!?])\s+", first):
            s = s.strip()
            if 25 <= len(s) <= max_len:
                out.append(s)
            if len(out) >= max_n:
                break
    return out[:max_n]


def _build_synthetic_snippet(content: str, lang: str) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", content) if 30 <= len(s) <= 100][:3]
    cmt = "# " if lang in ("python", "bash") else "// "
    body: list[str] = []
    for s in sentences:
        for chunk in textwrap.wrap(s, width=55):
            body.append(f"{cmt}{chunk}")
    if lang == "python":
        body += [
            "",
            "from fastapi import FastAPI",
            "app = FastAPI(title=\"jobhunter\")",
            "",
            "@app.get(\"/insights\")",
            "def insights() -> dict:",
            "    return {\"ready\": True}",
        ]
    elif lang == "bash":
        body += [
            "",
            "#!/usr/bin/env bash",
            "docker ps --format \"{{.Names}}\\t{{.Status}}\"",
            "systemctl status app",
        ]
    else:
        body += [
            "",
            "export function ship() {",
            "  return { ready: true };",
            "}",
        ]
    return "\n".join(body[:10])


# ---------------------------------------------------------------------------
# Syntax highlight (placeholder tokens to avoid cross-contamination)
# ---------------------------------------------------------------------------


PY_KEYWORDS = {
    "def", "return", "import", "from", "class", "if", "else", "elif",
    "for", "while", "try", "except", "finally", "with", "as", "yield",
    "lambda", "pass", "raise", "in", "not", "and", "or", "is", "None",
    "True", "False", "async", "await", "self", "cls",
}
BASH_KEYWORDS = {
    "set", "export", "source", "alias", "cd", "ls", "mkdir", "cp", "mv",
    "grep", "awk", "sed", "find", "ssh", "docker", "systemctl", "brew",
    "apt", "chmod", "chown", "tar", "curl", "wget", "git", "crontab",
    "kubectl", "sudo", "rsync", "tail", "head", "cat", "echo", "do",
    "done", "then", "fi", "function",
}
JS_KEYWORDS = {
    "const", "let", "var", "function", "return", "if", "else", "for",
    "while", "import", "export", "from", "default", "async", "await",
    "class", "new", "this", "true", "false", "null", "undefined",
    "interface", "type", "extends", "implements",
}


def _highlight(code: str, lang: str) -> str:
    if lang == "python":
        kws = PY_KEYWORDS
    elif lang == "bash":
        kws = BASH_KEYWORDS
    elif lang in ("tsx", "ts", "js", "jsx"):
        kws = JS_KEYWORDS
    else:
        return escape(code)

    TOK = {
        "STR_O": "\x01SO\x01", "STR_C": "\x01SC\x01",
        "CMT_O": "\x01CO\x01", "CMT_C": "\x01CC\x01",
        "NUM_O": "\x01NO\x01", "NUM_C": "\x01NC\x01",
        "KW_O":  "\x01KO\x01", "KW_C":  "\x01KC\x01",
    }
    text = code
    text = re.sub(
        r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')',
        lambda m: f'{TOK["STR_O"]}{m.group(1)}{TOK["STR_C"]}',
        text,
    )
    if lang in ("python", "bash"):
        text = re.sub(r"(#[^\n]*)", lambda m: f'{TOK["CMT_O"]}{m.group(1)}{TOK["CMT_C"]}', text)
    else:
        text = re.sub(r"(//[^\n]*)", lambda m: f'{TOK["CMT_O"]}{m.group(1)}{TOK["CMT_C"]}', text)
    for kw in kws:
        text = re.sub(rf'\b{re.escape(kw)}\b', f'{TOK["KW_O"]}{kw}{TOK["KW_C"]}', text)
    text = re.sub(r"\b(\d+(?:\.\d+)?)\b", lambda m: f'{TOK["NUM_O"]}{m.group(1)}{TOK["NUM_C"]}', text)

    safe = escape(text)
    return (
        safe
        .replace(TOK["STR_O"], '<span class="str">').replace(TOK["STR_C"], '</span>')
        .replace(TOK["CMT_O"], '<span class="cmt">').replace(TOK["CMT_C"], '</span>')
        .replace(TOK["NUM_O"], '<span class="num">').replace(TOK["NUM_C"], '</span>')
        .replace(TOK["KW_O"],  '<span class="kw">' ).replace(TOK["KW_C"],  '</span>')
    )


# ---------------------------------------------------------------------------
# Sidebar content by category
# ---------------------------------------------------------------------------


STEPS_BY_CAT: dict[str, list[dict[str, str]]] = {
    "sysadmin": [
        {"icon": "⏱", "title": "Cada 5 min", "body": "cron dispara chequeo de cada contenedor"},
        {"icon": "✓",  "title": "Si RUNNING", "body": "log silencioso · histórico en /var/log"},
        {"icon": "⚠",  "title": "Si DOWN",    "body": "alerta Telegram con el último error"},
    ],
    "python": [
        {"icon": "↘", "title": "Request",  "body": "FastAPI valida con Pydantic v2"},
        {"icon": "⚙", "title": "Service",  "body": "lógica desacoplada, fácil de testear"},
        {"icon": "✦", "title": "Persist",  "body": "SQLAlchemy 2.0 + transacciones"},
    ],
    "ai": [
        {"icon": "🎙", "title": "Input",   "body": "voz · texto · CSV todos en local"},
        {"icon": "✦",  "title": "LLM",     "body": "Ollama + Qwen estructuran a JSON"},
        {"icon": "✓",  "title": "Persist", "body": "Postgres + Redis cachea métricas"},
    ],
    "frontend": [
        {"icon": "✦", "title": "Compose", "body": "componentes con TypeScript estricto"},
        {"icon": "↻", "title": "State",   "body": "TanStack Query gestiona server state"},
        {"icon": "▲", "title": "Ship",    "body": "Vite + Vercel · preview por PR"},
    ],
    "project": [
        {"icon": "✏",  "title": "Diseñé",   "body": "stack que resuelve el problema"},
        {"icon": "⚒",  "title": "Construí", "body": "ciclo corto: API + UI + deploy"},
        {"icon": "↗",  "title": "Aprendí",  "body": "fallos en prod se vuelven docs"},
    ],
    "career": [
        {"icon": "→",  "title": "Sysadmin",  "body": "4 años operando sistemas críticos"},
        {"icon": "✦",  "title": "DAW",       "body": "ciclo + proyectos personales"},
        {"icon": "↗",  "title": "Hoy",       "body": "Full-Stack Python + AI shipping"},
    ],
}


CLOSERS = {
    "sysadmin": "El principio no cambia: monitorizar, actuar y notificar. Da igual el stack.",
    "python":   "FastAPI no es solo rápido, es claro. Y claro suele ser mantenible.",
    "ai":       "El modelo importa menos que el pipeline. Privacy-first cambia las reglas.",
    "frontend": "TypeScript estricto es gratis. Y se paga en bugs que no llegan a prod.",
    "project":  "Los proyectos no se terminan, se shippean. La iteración viene después.",
    "career":   "El sysadmin sabe arreglar lo que el dev no se atreve a tocar.",
}


SERVICES_BY_CAT: dict[str, list[dict[str, str]]] = {
    "sysadmin": [
        {"name": "Docker", "color": "#0db7ed"},
        {"name": "Nginx", "color": "#009639"},
        {"name": "Postgres", "color": "#336791"},
        {"name": "Redis", "color": "#dc382d"},
        {"name": "AD", "color": "#0078d4"},
        {"name": "Samba", "color": "#cb2027"},
    ],
    "ai": [
        {"name": "Ollama", "color": "#000000"},
        {"name": "Claude", "color": "#cc785c"},
        {"name": "Whisper", "color": "#10a37f"},
        {"name": "YOLO", "color": "#00d4aa"},
        {"name": "pgvector", "color": "#336791"},
        {"name": "FastAPI", "color": "#009688"},
    ],
    "python": [
        {"name": "FastAPI", "color": "#009688"},
        {"name": "Django", "color": "#0c4b33"},
        {"name": "Celery", "color": "#37b24d"},
        {"name": "Pydantic", "color": "#e92063"},
        {"name": "Docker", "color": "#0db7ed"},
        {"name": "Postgres", "color": "#336791"},
    ],
    "frontend": [
        {"name": "React", "color": "#61dafb"},
        {"name": "Vite", "color": "#646cff"},
        {"name": "Tailwind", "color": "#06b6d4"},
        {"name": "TypeScript", "color": "#3178c6"},
        {"name": "Vercel", "color": "#000000"},
        {"name": "Next.js", "color": "#000000"},
    ],
    "project": [
        {"name": "GitHub", "color": "#0d1117"},
        {"name": "Vercel", "color": "#000000"},
        {"name": "Render", "color": "#46e3b7"},
        {"name": "Stripe", "color": "#635bff"},
        {"name": "FastAPI", "color": "#009688"},
        {"name": "React", "color": "#61dafb"},
    ],
    # "career" se rellena en tiempo de ejecucion desde el perfil del usuario
    # (profile_context.career_badges()); no se hardcodean titulaciones de nadie.
    "career": [],
}


# ---------------------------------------------------------------------------
# Telegram mockup (sysadmin / ai only)
# ---------------------------------------------------------------------------


TELEGRAM_BY_CAT = {
    "sysadmin": [
        ("ok",   "[OK]   backup AD completado · 412 MB"),
        ("warn", "[WARN] docker nginx 2/3 healthchecks · reiniciando"),
    ],
    "ai": [
        ("ok",   "[OK]   entreno registrado · 4x8 banca 80 kg"),
        ("info", "[INFO] Whisper transcribió 14s en 1.2s · CPU 18%"),
    ],
}


# ---------------------------------------------------------------------------
# HTML build
# ---------------------------------------------------------------------------


def _build_html(topic: str, content: str, category: str) -> str:
    """Devlog template — code-first minimal.

    No big title / hook / bullets / closer (those repeat the post text).
    The image complements the post by showing the CODE at high resolution.
    """
    defs = CATEGORY_DEFS[category]
    accent = defs["accent"]
    accent_soft = defs["accent_soft"]
    tag = defs["tag"]
    tab = defs["tab"]
    lang = defs["lang"]

    # Code is the centerpiece — extract from post or synthesize.
    code = _detect_code(content) or _build_synthetic_snippet(content, lang)
    code_html = _highlight(code, lang)

    if category == "career":
        # Titulaciones/certificaciones del usuario, no las del autor original.
        services = profile_context.career_badges()
    else:
        services = SERVICES_BY_CAT.get(category, SERVICES_BY_CAT["project"])
    services_html = "".join(
        f'<div class="svc" style="--c:{s["color"]}">'
        f'<span class="svc-dot"></span><span class="svc-name">{escape(s["name"])}</span></div>'
        for s in services
    )

    hero_uri = _peepo_data_uri(PEEPO_HERO_BY_CAT.get(category, "peepoHappy"))
    peepo_hero_html = (
        f'<img class="peepo-mascot" src="{hero_uri}" alt="" />' if hero_uri else ""
    )
    author = _author_info()

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet" />
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ width: {WIDTH}px; height: {HEIGHT}px; }}
  body {{
    background: #08080c;
    color: #fafafa;
    font-family: 'Inter', -apple-system, sans-serif;
    position: relative;
    overflow: hidden;
    -webkit-font-smoothing: antialiased;
  }}
  .bg {{
    position: absolute; inset: 0;
    background:
      radial-gradient(70% 60% at 0% 0%, {accent_soft} 0%, transparent 55%),
      radial-gradient(50% 60% at 100% 100%, {accent_soft} 0%, transparent 60%),
      linear-gradient(180deg, #0a0a10 0%, #06070b 100%);
  }}
  .grain {{
    position: absolute; inset: 0;
    opacity: 0.4;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='1.2' stitchTiles='stitch'/></filter><rect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/></svg>");
    mix-blend-mode: overlay;
  }}

  .frame {{
    position: relative; z-index: 2;
    padding: 44px 52px 48px;
    height: 100%;
    display: grid;
    grid-template-rows: auto 1fr auto;
    gap: 22px;
  }}

  /* HEADER: badge + peepo */
  .header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
  }}
  .tag {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 7px 16px;
    background: {accent_soft};
    border: 1px solid {accent}55;
    border-radius: 999px;
    color: {accent};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
  }}
  .tag::before {{
    content: '';
    width: 7px; height: 7px;
    border-radius: 50%;
    background: {accent};
    box-shadow: 0 0 12px {accent};
  }}
  .peepo-mascot {{
    width: 100px; height: 100px;
    image-rendering: pixelated;
    filter: drop-shadow(0 8px 20px {accent}55);
    transform: translateY(-4px) rotate(-3deg);
  }}

  /* CODE PANEL — the centerpiece */
  .code-panel {{
    border-radius: 16px;
    background: linear-gradient(180deg, #0e1018 0%, #07090d 100%);
    border: 1px solid #1f2937;
    box-shadow: 0 28px 64px -16px rgba(0,0,0,0.7), 0 0 0 1px {accent_soft} inset;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }}
  .code-bar {{
    padding: 12px 18px;
    background: #11141b;
    border-bottom: 1px solid #1f2937;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .code-bar .dot {{ width: 12px; height: 12px; border-radius: 50%; }}
  .code-bar .dot.r {{ background: #ff5f56; }}
  .code-bar .dot.y {{ background: #ffbd2e; }}
  .code-bar .dot.g {{ background: #27c93f; }}
  .code-bar .tab {{
    margin-left: auto;
    color: #94a3b8;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
  }}
  pre.code {{
    margin: 0;
    padding: 26px 32px;
    flex: 1;
    font-family: 'JetBrains Mono', monospace;
    font-size: 19px;
    line-height: 1.6;
    color: #e2e8f0;
    white-space: pre;
    overflow: hidden;
  }}
  pre.code .kw  {{ color: {accent}; font-weight: 600; }}
  pre.code .str {{ color: #86efac; }}
  pre.code .cmt {{ color: #6b7280; font-style: italic; }}
  pre.code .num {{ color: #fbbf24; }}

  /* FOOTER */
  .foot {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
  }}
  .signature {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .avatar {{
    width: 38px; height: 38px;
    border-radius: 50%;
    background: linear-gradient(135deg, {accent}, #f0abfc);
    color: #0a0a0f;
    display: grid;
    place-items: center;
    font-weight: 800;
    font-size: 14px;
  }}
  .me .n {{ font-size: 14px; font-weight: 700; color: #fafafa; line-height: 1; }}
  .me .h {{ font-size: 11px; color: #6b7280; margin-top: 4px; }}

  .services {{
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    justify-content: center;
    max-width: 560px;
  }}
  .svc {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: rgba(255,255,255,0.03);
    border: 1px solid #1f2937;
    border-radius: 8px;
    font-size: 11px;
    color: #e2e8f0;
    font-family: 'JetBrains Mono', monospace;
  }}
  .svc-dot {{
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--c);
    box-shadow: 0 0 8px var(--c);
  }}

  .portfolio {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: {accent};
    font-weight: 600;
  }}
</style>
</head>
<body>
  <div class="bg"></div>
  <div class="grain"></div>
  <div class="frame">
    <div class="header">
      <div class="tag">{escape(tag)}</div>
      {peepo_hero_html}
    </div>

    <div class="code-panel">
      <div class="code-bar">
        <span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>
        <span class="tab">{escape(tab)}</span>
      </div>
      <pre class="code">{code_html}</pre>
    </div>

    <div class="foot">
      <div class="signature">
        <div class="avatar">{escape(author["initials"])}</div>
        <div class="me">
          <div class="n">{escape(author["name"])}</div>
          <div class="h">{escape(author["title"])}</div>
        </div>
      </div>
      <div class="services">{services_html}</div>
      <div class="portfolio">{escape(author["portfolio"])}</div>
    </div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Render with Playwright CLI
# ---------------------------------------------------------------------------


def _render_with_playwright(html: str, output_path: Path) -> bool:
    if shutil.which("npx") is None:
        logger.warning("npx not found, cannot render HTML images")
        return False
    tmp_html = output_path.with_suffix(".html")
    tmp_html.write_text(html, encoding="utf-8")
    try:
        cmd = [
            "npx",
            "--yes",
            "-p",
            "playwright@latest",
            "playwright",
            "screenshot",
            "--viewport-size",
            f"{WIDTH},{HEIGHT}",
            "--wait-for-timeout=1100",  # Google Fonts time to load
            tmp_html.as_uri(),
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=90, text=True)
        if result.returncode != 0:
            logger.warning(
                "playwright screenshot failed (rc=%s): %s",
                result.returncode,
                result.stderr[:500],
            )
            return False
        return output_path.exists() and output_path.stat().st_size > 1000
    except Exception as e:  # noqa: BLE001
        logger.warning("playwright invocation failed: %s", e)
        return False
    finally:
        try:
            tmp_html.unlink()
        except FileNotFoundError:
            pass


def generate_post_image_html(post_id: int, post_data: dict[str, Any]) -> Path | None:
    try:
        topic = (post_data.get("topic") or "Untitled").replace("[ext-error]", "").strip()
        content = (post_data.get("content") or "").replace("[ext-error]", "").strip()
        kind = (post_data.get("kind") or "personal").lower()
        category = _detect_category(content, post_data.get("category"))

        out_dir = settings.data_path / "posts" / "images"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"post_{post_id}.png"

        if kind == "trending":
            source_url = (post_data.get("source_url") or "").strip()
            original_title = (post_data.get("original_title") or "").strip()
            source_summary = (post_data.get("source_summary") or "").strip()
            hn_score = int(post_data.get("hn_score") or 0)
            hn_comments = int(post_data.get("hn_comments") or 0)
            html = _build_news_html(
                topic, content, category, source_url,
                original_title=original_title,
                source_summary=source_summary,
                hn_score=hn_score, hn_comments=hn_comments,
            )
        else:
            html = _build_html(topic, content, category)

        ok = _render_with_playwright(html, output_path)
        if not ok:
            return None
        logger.info(
            "post image (%s) %s -> %s bytes",
            kind, output_path, output_path.stat().st_size,
        )
        return output_path
    except Exception as e:  # noqa: BLE001
        logger.exception("generate_post_image_html failed for %s: %s", post_id, e)
        return None


# ---------------------------------------------------------------------------
# NEWS / TRENDING template (editorial style, distinct from infographic)
# ---------------------------------------------------------------------------

NEWS_PEEPO_BY_CAT: dict[str, str] = {
    "ai":       "owonerd",     # AI nerd
    "sysadmin": "peepoHappy",
    "python":   "peepoPls",
    "frontend": "OWO",
    "project":  "PepePls",
    "career":   "peepoHappy",
}


def _build_news_html(
    topic: str,
    content: str,
    category: str,
    source_url: str = "",
    original_title: str = "",
    source_summary: str = "",
    hn_score: int = 0,
    hn_comments: int = 0,
) -> str:
    """Trending template — browser-preview card style.

    Shows the ORIGINAL article (domain + title + HN stats) — not a copy of
    the post text. The post text + image complement each other on LinkedIn.
    """
    accent = "#ec4899"          # magenta
    accent_2 = "#8b5cf6"        # violet
    accent_soft = "rgba(236, 72, 153, 0.15)"

    # Domain extraction
    src_domain = ""
    if source_url:
        m = re.search(r"https?://([^/]+)", source_url)
        if m:
            src_domain = m.group(1).replace("www.", "")

    # Favicon-like letter from domain
    fav_letter = (src_domain[:1].upper() if src_domain else "?")

    # Article title to display (prefer original article title, fallback to post topic)
    article_title = (original_title or topic).strip()
    if len(article_title) > 110:
        article_title = article_title[:107].rsplit(" ", 1)[0] + "…"

    # Short summary text under the title (og:description from the source page)
    summary_text = (source_summary or "").strip()
    if len(summary_text) > 230:
        summary_text = summary_text[:227].rsplit(" ", 1)[0] + "…"
    summary_html = (
        f'<div class="article-summary">{escape(summary_text)}</div>'
        if summary_text
        else ""
    )

    peepo_name = NEWS_PEEPO_BY_CAT.get(category, "peepoHappy")
    peepo_uri = _peepo_data_uri(peepo_name)
    peepo_html = (
        f'<img class="peepo-mascot" src="{peepo_uri}" alt="" />' if peepo_uri else ""
    )

    stats_html = ""
    if hn_score or hn_comments:
        stats_html = (
            '<div class="hn-stats">'
            f'<div class="stat"><div class="stat-val">{hn_score}</div><div class="stat-label">▲ HN points</div></div>'
            f'<div class="stat"><div class="stat-val">{hn_comments}</div><div class="stat-label">💬 comments</div></div>'
            f'<div class="stat"><div class="stat-val">24h</div><div class="stat-label">⏱ last day</div></div>'
            '</div>'
        )

    author = _author_info()

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet" />
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ width: {WIDTH}px; height: {HEIGHT}px; }}
  body {{
    background: #07060c;
    color: #fafafa;
    font-family: 'Inter', -apple-system, sans-serif;
    position: relative;
    overflow: hidden;
    -webkit-font-smoothing: antialiased;
  }}
  .bg {{
    position: absolute; inset: 0;
    background:
      radial-gradient(65% 70% at 100% 0%, {accent_soft} 0%, transparent 55%),
      radial-gradient(60% 60% at 0% 100%, rgba(139, 92, 246, 0.18) 0%, transparent 55%),
      linear-gradient(180deg, #0c0814 0%, #050308 100%);
  }}
  .grain {{
    position: absolute; inset: 0;
    opacity: 0.4;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='1.4' stitchTiles='stitch'/></filter><rect width='100%25' height='100%25' filter='url(%23n)' opacity='0.06'/></svg>");
    mix-blend-mode: overlay;
  }}
  .stripe {{
    position: absolute; top: 0; left: 0; right: 0; height: 5px;
    background: linear-gradient(90deg, {accent} 0%, {accent_2} 50%, {accent} 100%);
  }}

  .frame {{
    position: relative; z-index: 2;
    padding: 56px 56px 50px;
    height: 100%;
    display: grid;
    grid-template-rows: auto 1fr auto;
    gap: 28px;
  }}

  /* HEADER: badge + peepo */
  .header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .tag {{
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 9px 18px;
    background: {accent};
    color: #1a0014;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 900;
    letter-spacing: 0.3em;
    text-transform: uppercase;
  }}
  .peepo-mascot {{
    width: 110px; height: 110px;
    image-rendering: pixelated;
    filter: drop-shadow(0 10px 24px {accent}66);
    transform: translateY(-8px) rotate(-4deg);
  }}

  /* BROWSER CARD — the visual centerpiece */
  .browser-card {{
    background: linear-gradient(180deg, #15101e 0%, #0f0b18 100%);
    border: 1px solid #312240;
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 24px 60px -20px rgba(236,72,153,0.35), 0 0 0 1px {accent_soft} inset;
    display: flex;
    flex-direction: column;
  }}
  .browser-bar {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 18px;
    border-bottom: 1px solid #2a1a3a;
    background: rgba(0,0,0,0.25);
  }}
  .browser-bar .dot {{ width: 11px; height: 11px; border-radius: 50%; }}
  .browser-bar .dot.r {{ background: #ff5f56; }}
  .browser-bar .dot.y {{ background: #ffbd2e; }}
  .browser-bar .dot.g {{ background: #27c93f; }}
  .browser-bar .urlbar {{
    margin-left: 12px;
    flex: 1;
    background: rgba(255,255,255,0.04);
    border: 1px solid #2a1a3a;
    border-radius: 999px;
    padding: 6px 16px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: #cbd5e1;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .browser-bar .urlbar::before {{
    content: '🔒';
    font-size: 10px;
  }}

  .browser-body {{
    flex: 1;
    padding: 36px 40px 32px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 22px;
  }}
  .site-row {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}
  .favicon {{
    width: 48px; height: 48px;
    border-radius: 10px;
    background: linear-gradient(135deg, {accent}, {accent_2});
    display: grid;
    place-items: center;
    font-weight: 900;
    font-size: 22px;
    color: #1a0014;
    flex-shrink: 0;
  }}
  .site-meta .domain {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    color: {accent};
    font-weight: 700;
    letter-spacing: 0.02em;
  }}
  .site-meta .source-label {{
    font-size: 10.5px;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    margin-top: 4px;
  }}
  .article-title {{
    font-size: 32px;
    font-weight: 800;
    letter-spacing: -0.02em;
    line-height: 1.18;
    color: #fafafa;
  }}
  .article-summary {{
    font-size: 16px;
    color: #cbd5e1;
    line-height: 1.5;
    font-weight: 400;
    border-left: 3px solid {accent};
    padding-left: 14px;
  }}

  .hn-stats {{
    display: flex;
    gap: 14px;
    padding-top: 18px;
    border-top: 1px solid #2a1a3a;
  }}
  .stat {{
    flex: 1;
    background: rgba(255,255,255,0.03);
    border: 1px solid #2a1a3a;
    border-radius: 10px;
    padding: 12px 16px;
  }}
  .stat-val {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 24px;
    font-weight: 700;
    color: {accent};
    letter-spacing: -0.02em;
  }}
  .stat-label {{
    font-size: 10px;
    color: #94a3b8;
    margin-top: 4px;
    letter-spacing: 0.04em;
  }}

  /* FOOTER */
  .foot {{
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .signature {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .avatar {{
    width: 40px; height: 40px;
    border-radius: 50%;
    background: linear-gradient(135deg, {accent}, {accent_2});
    color: #fafafa;
    display: grid;
    place-items: center;
    font-weight: 800;
    font-size: 14px;
  }}
  .me .n {{ font-size: 14px; font-weight: 700; color: #fafafa; line-height: 1; }}
  .me .h {{ font-size: 11px; color: #6b7280; margin-top: 4px; }}
  .portfolio {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: {accent};
    font-weight: 600;
  }}
</style>
</head>
<body>
  <div class="bg"></div>
  <div class="grain"></div>
  <div class="stripe"></div>
  <div class="frame">

    <div class="header">
      <span class="tag">⚡ Trending tech · 24h</span>
      {peepo_html}
    </div>

    <div class="browser-card">
      <div class="browser-bar">
        <span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>
        <div class="urlbar">{escape(source_url[:90] if source_url else 'news.ycombinator.com')}</div>
      </div>
      <div class="browser-body">
        <div class="site-row">
          <div class="favicon">{escape(fav_letter)}</div>
          <div class="site-meta">
            <div class="domain">{escape(src_domain or "news.ycombinator.com")}</div>
            <div class="source-label">via Hacker News · top story</div>
          </div>
        </div>
        <div class="article-title">{escape(article_title)}</div>
        {summary_html}
        {stats_html}
      </div>
    </div>

    <div class="foot">
      <div class="signature">
        <div class="avatar">{escape(author["initials"])}</div>
        <div class="me">
          <div class="n">{escape(author["name"])}</div>
          <div class="h">{escape(author["title"])}</div>
        </div>
      </div>
      <div class="portfolio">{escape(author["portfolio"])}</div>
    </div>
  </div>
</body>
</html>"""
