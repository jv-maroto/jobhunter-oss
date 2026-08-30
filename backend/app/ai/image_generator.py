"""Generador de imagenes para posts LinkedIn — v2 con 3 plantillas distintas.

- Code editor mockup (python/ai/frontend): ventana de IDE con código
- Terminal style (sysadmin): pantalla negra con prompt $ y comandos
- Editorial (project/career): tipografía grande, una frase clave + brand

Sin Playwright. Solo Pillow. 0 dependencias externas.
"""

from __future__ import annotations

import logging
import re
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.ai import profile_context
from app.config import settings

logger = logging.getLogger(__name__)


WIDTH = 1200
HEIGHT = 628

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

_HELVETICA_TTC = "/System/Library/Fonts/HelveticaNeue.ttc"
_MENLO_TTC = "/System/Library/Fonts/Menlo.ttc"
_AVENIR_TTC = "/System/Library/Fonts/Avenir.ttc"
# HelveticaNeue.ttc font indices: 0=Thin 4=Regular 5=Italic 6=Bold 7=BoldItalic
# 8=CondensedBold 9=CondensedBlack
# Menlo.ttc: 0=Regular 1=Bold 2=Italic 3=BoldItalic


def _font(size: int, *, bold: bool = False, ultra: bool = False) -> ImageFont.FreeTypeFont:
    """Best-available system font for headlines & body.

    HelveticaNeue.ttc face indices:
        0 = UltraLight, 1 = UltraLightItalic
        2 = Thin,       3 = ThinItalic
        4 = Light,      5 = LightItalic          ← (we previously used 4 as "Regular" wrongly)
        6 = Regular,    7 = Italic               ← this is the actual Regular
        8 = Medium,     9 = MediumItalic
        10 = Bold,      11 = BoldItalic
        12 = CondensedBold, 13 = CondensedBlack
    """
    candidates: list[tuple[str, int]] = []
    if Path(_HELVETICA_TTC).exists():
        if ultra:
            candidates.append((_HELVETICA_TTC, 13))  # CondensedBlack
        elif bold:
            candidates.append((_HELVETICA_TTC, 10))  # Bold
        else:
            candidates.append((_HELVETICA_TTC, 6))  # Regular
    fallback = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Geneva.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for path in fallback:
        idx = 0
        candidates.append((path, idx))

    for path, idx in candidates:
        if not Path(path).exists():
            continue
        try:
            return ImageFont.truetype(path, size, index=idx)
        except Exception:  # noqa: BLE001
            try:
                return ImageFont.truetype(path, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def _mono(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    if Path(_MENLO_TTC).exists():
        try:
            return ImageFont.truetype(_MENLO_TTC, size, index=1 if bold else 0)
        except Exception:  # noqa: BLE001
            pass
    for p in ["/System/Library/Fonts/Monaco.ttf", "/System/Library/Fonts/Courier.ttc"]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Text cleanup
# ---------------------------------------------------------------------------


def _sanitize(text: str) -> str:
    text = re.sub(r"\[ext-error\][^\n]*\n?", "", text)
    text = (
        text.replace("→", " > ")
        .replace("←", " < ")
        .replace("↑", " ^ ")
        .replace("↓", " v ")
        .replace("…", "...")
        .replace("•", "-")
        .replace(" ", " ")
    )
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _detect_category(content: str, category: str | None = None) -> str:
    if category and category.lower() in (
        "python",
        "ai",
        "sysadmin",
        "frontend",
        "project",
        "career",
    ):
        return category.lower()
    text = content.lower()
    if any(k in text for k in ["ollama", "llm", "claude", "gpt", "whisper", "yolo", "embeddings"]):
        return "ai"
    if any(k in text for k in ["bash", "ssh", "active directory", "windows server", "linux", "scripts", "ldap", "cron", "systemd", "ad ", "rdp"]):
        return "sysadmin"
    if any(k in text for k in ["react", "tailwind", "vite", "next.js", "typescript ", "tsx", "frontend"]):
        return "frontend"
    if any(k in text for k in ["fastapi", "django", "python", "celery", "pydantic", "sqlalchemy"]):
        return "python"
    projects = profile_context.project_keywords()
    if projects and any(k in text for k in projects):
        return "project"
    if any(k in text for k in ["entrevista", "carrera", "transición", "aprendí", "lecciones"]):
        return "career"
    return "project"


def _detect_code(content: str) -> tuple[str | None, str]:
    """Returns (code, language) or (None, '')."""
    m = re.search(r"```([a-zA-Z+]*)\n(.+?)```", content, re.DOTALL)
    if not m:
        return None, ""
    return m.group(2).strip(), (m.group(1) or "").strip()


def _detect_commands(content: str) -> list[str]:
    """Find lines that look like shell commands (start with $, sudo, mkdir, etc)."""
    cmds: list[str] = []
    for line in content.split("\n"):
        s = line.strip().lstrip("$ ")
        if not s or len(s) < 4 or len(s) > 90:
            continue
        if re.match(r"^(sudo|cd |ls |mkdir |cp |mv |grep |awk |sed |find |ssh |docker|systemctl|brew|apt|yum|chmod|chown|tar|curl|wget|git|kubectl|netstat|ps |ip |dig |nmap|rsync|crontab|journalctl|launchctl|defaults|killall|pkill|ln |touch|cat |tail |head |less |more |vim |nano |export |source |alias|history|whoami|id |uname|df |du |free|top|htop|kill |nohup|env|set |unset|echo )", s, re.IGNORECASE):
            cmds.append(s)
        if len(cmds) >= 6:
            break
    return cmds


def _key_sentence(content: str) -> str:
    """Pick the most impactful first sentence (hook) from the post."""
    cleaned = re.sub(r"```.+?```", "", content, flags=re.DOTALL)
    # Take the first 1-2 sentences of the first paragraph
    first_para = cleaned.strip().split("\n\n")[0]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", first_para)]
    if not sentences:
        return content[:140]
    chosen = sentences[0]
    if len(chosen) < 50 and len(sentences) > 1:
        chosen = f"{chosen} {sentences[1]}"
    return chosen[:240]


# ---------------------------------------------------------------------------
# Common painting utilities
# ---------------------------------------------------------------------------

def _draw_text_wrapped(
    draw: ImageDraw.ImageDraw,
    pos: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    max_width: int,
    line_height: float = 1.18,
) -> int:
    x, y = pos
    avg_char = max(8, int(font.size * 0.5))
    chars_per_line = max(8, max_width // avg_char)
    cur_y = y
    line_px = int(font.size * line_height)
    for para in text.split("\n"):
        if not para.strip():
            cur_y += int(line_px * 0.5)
            continue
        for line in textwrap.wrap(para, width=chars_per_line):
            draw.text((x, cur_y), line, font=font, fill=fill)
            cur_y += line_px
    return cur_y


def _measure_text(font: ImageFont.FreeTypeFont, text: str) -> tuple[int, int]:
    tmp = Image.new("RGBA", (1, 1))
    bbox = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_signature(img: Image.Image, accent: tuple, accent2: tuple) -> None:
    """JM avatar + name + portfolio URL footer."""
    draw = ImageDraw.Draw(img)
    y = HEIGHT - 60
    x = 56

    # Avatar circle with JM
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.ellipse((x, y - 20, x + 36, y + 16), fill=(*accent, 255))
    # Pillow fallback: keeps text empty when no CV is configured to avoid leaking placeholder text into generated images
    try:
        from app.services import load_cv_master
        _cv = load_cv_master() or {}
        _p = _cv.get("personal", {}) or {}
        _author_name = (_p.get("name") or "").strip() or "Your Name"
        _author_title = (_p.get("title") or "").strip() or "Engineer"
        _author_portfolio = (_p.get("portfolio") or "").replace("https://", "").replace("http://", "").strip()
        _parts = [w for w in _author_name.split() if w]
        _initials = "".join(w[0] for w in _parts[:2]).upper() or "?"
    except Exception:
        _author_name, _author_title, _author_portfolio, _initials = "Your Name", "Engineer", "", "?"

    odraw.text((x + 7, y - 13), _initials, font=_font(13, bold=True), fill=(10, 10, 14))
    img.alpha_composite(overlay)

    name_font = _font(15, bold=True)
    handle_font = _font(11)
    draw.text((x + 48, y - 18), _author_name, font=name_font, fill=(248, 250, 252))
    draw.text((x + 48, y), _author_title, font=handle_font, fill=(148, 163, 184))

    portfolio = _author_portfolio
    w, _ = _measure_text(handle_font, portfolio)
    draw.text(
        (WIDTH - 56 - w, y - 6),
        portfolio,
        font=_font(12, bold=True),
        fill=accent2,
    )


def _draw_brand_corner(img: Image.Image) -> None:
    """Small brand tag in top-right corner."""
    draw = ImageDraw.Draw(img)
    font = _font(11, bold=True)
    label = "JOBHUNTER · DEVLOG"
    w, _ = _measure_text(font, label)
    draw.text((WIDTH - 56 - w, 46), label, font=font, fill=(255, 255, 255, 90))


# ---------------------------------------------------------------------------
# Template 1: CODE EDITOR (Python / AI / Frontend)
# ---------------------------------------------------------------------------

CODE_THEMES = {
    "python": {
        "bg": (15, 23, 42),
        "accent": (96, 165, 250),
        "accent2": (52, 211, 153),
        "tag_text": "PYTHON",
    },
    "ai": {
        "bg": (24, 24, 36),
        "accent": (192, 132, 252),
        "accent2": (244, 114, 182),
        "tag_text": "AI / LLM",
    },
    "frontend": {
        "bg": (22, 22, 32),
        "accent": (251, 191, 36),
        "accent2": (248, 113, 113),
        "tag_text": "FRONTEND",
    },
}

KEYWORDS = re.compile(
    r"\b(def|return|import|from|class|if|else|elif|for|while|try|except|finally|with|as|yield|lambda|pass|raise|in|not|and|or|is|None|True|False|async|await|await|self|cls)\b"
)
STRINGS = re.compile(r"(\".*?\"|'.*?'|f\".*?\"|f'.*?')")
COMMENTS = re.compile(r"(#.*?$)", re.MULTILINE)
NUMBERS = re.compile(r"\b(\d+(?:\.\d+)?)\b")


def _render_syntax_line(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    line: str,
    font: ImageFont.FreeTypeFont,
    theme: dict,
) -> None:
    """Very lightweight syntax coloring for Python-ish lines."""
    base_color = (226, 232, 240)
    accent = theme["accent"]
    string_c = (134, 239, 172)
    comment_c = (107, 114, 128)
    number_c = (251, 191, 36)

    # Mark tokens by position to avoid double-color
    spans: list[tuple[int, int, tuple]] = []
    for m in COMMENTS.finditer(line):
        spans.append((m.start(), m.end(), comment_c))
    for m in STRINGS.finditer(line):
        spans.append((m.start(), m.end(), string_c))
    for m in KEYWORDS.finditer(line):
        spans.append((m.start(), m.end(), accent))
    for m in NUMBERS.finditer(line):
        spans.append((m.start(), m.end(), number_c))

    # Resolve overlaps: comments / strings win over keywords.
    spans.sort(key=lambda s: s[0])
    pos = 0
    cx = x
    char_w, _ = _measure_text(font, " ")
    while pos < len(line):
        # Find the next span that starts at or after pos
        nxt = next((s for s in spans if s[1] > pos and s[0] >= pos), None)
        if nxt and nxt[0] == pos:
            # Render this span
            chunk = line[nxt[0] : nxt[1]]
            draw.text((cx, y), chunk, font=font, fill=nxt[2])
            cw, _ = _measure_text(font, chunk)
            cx += cw
            pos = nxt[1]
        else:
            # Render up to the next span start (or end of line)
            end = nxt[0] if nxt else len(line)
            chunk = line[pos:end]
            draw.text((cx, y), chunk, font=font, fill=base_color)
            cw, _ = _measure_text(font, chunk)
            cx += cw
            pos = end


def _render_code_editor(
    topic: str,
    code: str,
    theme: dict,
) -> Image.Image:
    img = Image.new("RGBA", (WIDTH, HEIGHT), (10, 12, 18, 255))

    # Gradient backdrop
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for i in range(35, 0, -1):
        r = i * 30
        alpha = int(70 * (i / 35)) // 4
        odraw.ellipse((-r, -r, r, r), fill=(*theme["accent"], alpha))
        odraw.ellipse((WIDTH - r, HEIGHT - r, WIDTH + r, HEIGHT + r), fill=(*theme["accent2"], alpha))
    overlay = overlay.filter(ImageFilter.GaussianBlur(60))
    img.alpha_composite(overlay)

    # Subtle grid
    gov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(gov)
    for x in range(0, WIDTH, 56):
        gdraw.line([(x, 0), (x, HEIGHT)], fill=(255, 255, 255, 8), width=1)
    for y in range(0, HEIGHT, 56):
        gdraw.line([(0, y), (WIDTH, y)], fill=(255, 255, 255, 8), width=1)
    img.alpha_composite(gov)

    draw = ImageDraw.Draw(img)

    # Tag pill
    pill_y = 52
    pill_label = theme["tag_text"]
    pill_font = _font(13, bold=True)
    pw, ph = _measure_text(pill_font, pill_label)
    pill_box = (56, pill_y, 56 + pw + 44, pill_y + ph + 18)
    pov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pov)
    pdraw.rounded_rectangle(
        pill_box,
        radius=20,
        fill=(*theme["accent"], 25),
        outline=(*theme["accent"], 180),
        width=2,
    )
    # Dot
    dot_x = 70
    dot_y = pill_y + ph // 2 + 9
    pdraw.ellipse((dot_x - 4, dot_y - 4, dot_x + 4, dot_y + 4), fill=theme["accent"])
    pdraw.text((dot_x + 12, pill_y + 8), pill_label, font=pill_font, fill=theme["accent"])
    img.alpha_composite(pov)

    _draw_brand_corner(img)

    # Title
    title_font = _font(36, bold=True)
    title_y = pill_y + ph + 50
    title_end = _draw_text_wrapped(
        draw,
        (56, title_y),
        topic,
        title_font,
        (250, 250, 250),
        max_width=WIDTH - 112,
        line_height=1.12,
    )

    # Editor window
    win_x = 56
    win_y = title_end + 30
    win_w = WIDTH - 112
    win_h = HEIGHT - win_y - 100
    if win_h < 160:
        win_h = 160
    wov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(wov)
    # Outer shadow
    wdraw.rounded_rectangle(
        (win_x - 4, win_y - 4, win_x + win_w + 4, win_y + win_h + 4),
        radius=18,
        fill=(0, 0, 0, 90),
    )
    # Editor body
    wdraw.rounded_rectangle(
        (win_x, win_y, win_x + win_w, win_y + win_h),
        radius=14,
        fill=(15, 18, 27, 245),
        outline=(*theme["accent"], 90),
        width=1,
    )
    # Title bar
    bar_h = 32
    wdraw.rounded_rectangle(
        (win_x, win_y, win_x + win_w, win_y + bar_h),
        radius=14,
        fill=(22, 26, 38, 255),
    )
    wdraw.rectangle(
        (win_x, win_y + bar_h - 14, win_x + win_w, win_y + bar_h),
        fill=(22, 26, 38, 255),
    )
    # Three dots
    dot_colors = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]
    for i, c in enumerate(dot_colors):
        cx = win_x + 18 + i * 18
        cy = win_y + bar_h // 2
        wdraw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=c)
    # Tab label
    tab_label = "main.py" if "python" in pill_label.lower() else (
        "agent.py" if "ai" in pill_label.lower() else "app.tsx"
    )
    tab_font = _mono(12)
    tw, _ = _measure_text(tab_font, tab_label)
    wdraw.text(
        (win_x + win_w // 2 - tw // 2, win_y + bar_h // 2 - 7),
        tab_label,
        font=tab_font,
        fill=(148, 163, 184),
    )
    img.alpha_composite(wov)

    # Code lines
    code_font = _mono(15)
    line_h = int(code_font.size * 1.55)
    lines = code.split("\n")[:12]
    code_x = win_x + 60
    code_y = win_y + bar_h + 18

    gutter_x = win_x + 16
    gutter_font = _mono(13)
    for i, line in enumerate(lines):
        ln_y = code_y + i * line_h
        if ln_y > win_y + win_h - 24:
            break
        # Line number
        draw.text(
            (gutter_x, ln_y),
            f"{i+1:>2}",
            font=gutter_font,
            fill=(75, 85, 105),
        )
        _render_syntax_line(draw, code_x, ln_y, line, code_font, theme)

    _draw_signature(img, theme["accent"], theme["accent2"])
    return img


# ---------------------------------------------------------------------------
# Template 2: TERMINAL (sysadmin)
# ---------------------------------------------------------------------------

def _render_terminal(
    topic: str,
    commands: list[str],
) -> Image.Image:
    accent = (52, 211, 153)
    accent2 = (251, 191, 36)
    img = Image.new("RGBA", (WIDTH, HEIGHT), (6, 7, 12, 255))

    # Subtle CRT-style scanlines
    sov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sov)
    for y in range(0, HEIGHT, 3):
        sdraw.line([(0, y), (WIDTH, y)], fill=(0, 255, 100, 5), width=1)
    img.alpha_composite(sov)

    # Soft green glow corner
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    for i in range(40, 0, -1):
        r = i * 25
        alpha = int(80 * (i / 40)) // 5
        gdraw.ellipse(
            (WIDTH // 2 - r, HEIGHT - r // 2, WIDTH // 2 + r, HEIGHT + r // 2),
            fill=(*accent, alpha),
        )
    glow = glow.filter(ImageFilter.GaussianBlur(50))
    img.alpha_composite(glow)

    draw = ImageDraw.Draw(img)

    # Tag
    pill_label = "SYSADMIN"
    pill_font = _font(13, bold=True)
    pw, ph = _measure_text(pill_font, pill_label)
    pill_box = (56, 52, 56 + pw + 44, 52 + ph + 18)
    pov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pov)
    pdraw.rounded_rectangle(
        pill_box, radius=20, fill=(*accent, 22), outline=(*accent, 180), width=2
    )
    pdraw.ellipse((70 - 4, 52 + ph // 2 + 5, 70 + 4, 52 + ph // 2 + 13), fill=accent)
    pdraw.text((82, 60), pill_label, font=pill_font, fill=accent)
    img.alpha_composite(pov)
    _draw_brand_corner(img)

    # Title
    title_font = _font(40, bold=True)
    title_end = _draw_text_wrapped(
        draw,
        (56, 130),
        topic,
        title_font,
        (240, 253, 244),
        max_width=WIDTH - 112,
        line_height=1.1,
    )

    # Terminal window
    win_x = 56
    win_y = title_end + 28
    win_w = WIDTH - 112
    win_h = HEIGHT - win_y - 100

    tov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(tov)
    tdraw.rounded_rectangle(
        (win_x, win_y, win_x + win_w, win_y + win_h),
        radius=12,
        fill=(0, 0, 0, 235),
        outline=(*accent, 70),
        width=1,
    )
    # Title bar
    bar_h = 28
    tdraw.rounded_rectangle(
        (win_x, win_y, win_x + win_w, win_y + bar_h),
        radius=12,
        fill=(16, 20, 24, 255),
    )
    tdraw.rectangle(
        (win_x, win_y + bar_h - 12, win_x + win_w, win_y + bar_h),
        fill=(16, 20, 24, 255),
    )
    # Three dots
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = win_x + 16 + i * 16
        cy = win_y + bar_h // 2
        tdraw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=c)
    tab_font = _mono(11)
    tab_label = profile_context.terminal_label()
    tw, _ = _measure_text(tab_font, tab_label)
    tdraw.text(
        (win_x + win_w // 2 - tw // 2, win_y + bar_h // 2 - 6),
        tab_label,
        font=tab_font,
        fill=(148, 163, 184),
    )
    img.alpha_composite(tov)

    # Commands
    cmd_font = _mono(15)
    out_font = _mono(13)
    line_h = int(cmd_font.size * 1.55)
    cur_y = win_y + bar_h + 20
    cx = win_x + 22

    for cmd in commands[:6]:
        if cur_y > win_y + win_h - 30:
            break
        # Prompt
        draw.text((cx, cur_y), "$", font=cmd_font, fill=accent)
        draw.text((cx + 22, cur_y), cmd, font=cmd_font, fill=(240, 253, 244))
        cur_y += line_h
        # Fake one-line output
        snippet = "ok" if "echo" in cmd.lower() else "..."
        draw.text((cx, cur_y), snippet, font=out_font, fill=(94, 234, 212))
        cur_y += int(line_h * 0.9)

    # Final blinking cursor
    if cur_y < win_y + win_h - 30:
        draw.text((cx, cur_y), "$", font=cmd_font, fill=accent)
        cur_block_x = cx + 22
        cur_block_y = cur_y + 4
        draw.rectangle(
            (cur_block_x, cur_block_y, cur_block_x + 10, cur_block_y + 16),
            fill=accent,
        )

    _draw_signature(img, accent, accent2)
    return img


# ---------------------------------------------------------------------------
# Template 3: EDITORIAL (project / career / fallback)
# ---------------------------------------------------------------------------

def _render_editorial(topic: str, hook: str, category: str) -> Image.Image:
    palettes = {
        "project": {"accent": (34, 211, 238), "accent2": (163, 230, 53), "tag": "PROJECT"},
        "career": {"accent": (163, 230, 53), "accent2": (34, 211, 238), "tag": "CAREER"},
    }
    pal = palettes.get(category, palettes["project"])
    accent = pal["accent"]
    accent2 = pal["accent2"]

    img = Image.new("RGBA", (WIDTH, HEIGHT), (10, 11, 18, 255))

    # Big soft blobs (the actual visual interest)
    blob = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(blob)
    bdraw.ellipse((-220, -160, 500, 480), fill=(*accent, 90))
    bdraw.ellipse((720, 250, 1450, 900), fill=(*accent2, 70))
    blob = blob.filter(ImageFilter.GaussianBlur(120))
    img.alpha_composite(blob)

    # Halftone-ish noise (thin diagonal grain)
    nov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ndraw = ImageDraw.Draw(nov)
    for y in range(0, HEIGHT, 4):
        for x in range(0, WIDTH, 4):
            if ((x + y) % 8) == 0:
                ndraw.point((x, y), fill=(255, 255, 255, 14))
    img.alpha_composite(nov)

    draw = ImageDraw.Draw(img)

    # Left accent bar
    bar = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bdraw2 = ImageDraw.Draw(bar)
    bdraw2.rectangle((56, 110, 60, HEIGHT - 110), fill=(*accent, 230))
    img.alpha_composite(bar)

    # Tag
    pill_label = pal["tag"]
    pill_font = _font(13, bold=True)
    pw, ph = _measure_text(pill_font, pill_label)
    pill_box = (84, 52, 84 + pw + 44, 52 + ph + 18)
    pov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pov)
    pdraw.rounded_rectangle(
        pill_box, radius=20, fill=(*accent, 28), outline=(*accent, 200), width=2
    )
    pdraw.ellipse((98 - 4, 52 + ph // 2 + 5, 98 + 4, 52 + ph // 2 + 13), fill=accent)
    pdraw.text((110, 60), pill_label, font=pill_font, fill=accent)
    img.alpha_composite(pov)
    _draw_brand_corner(img)

    # Hook quote — massive
    quote_font = _font(54, bold=True)
    # Wrap with very generous width
    quote_text = '"' + hook.strip().rstrip(".") + '"'
    quote_end = _draw_text_wrapped(
        draw,
        (90, 140),
        quote_text,
        quote_font,
        (250, 250, 252),
        max_width=WIDTH - 180,
        line_height=1.1,
    )

    # Topic small under the quote
    topic_font = _font(18, bold=True)
    topic_y = quote_end + 24
    if topic_y > HEIGHT - 130:
        topic_y = HEIGHT - 130
    draw.text(
        (90, topic_y),
        topic.upper(),
        font=topic_font,
        fill=accent2,
    )

    _draw_signature(img, accent, accent2)
    return img


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def generate_post_image(post_id: int, post_data: dict[str, Any]) -> Path | None:
    try:
        topic = _sanitize(post_data.get("topic", "Untitled"))
        content = _sanitize(post_data.get("content", ""))
        category = _detect_category(content, post_data.get("category"))

        out_dir = settings.data_path / "posts" / "images"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"post_{post_id}.png"

        code, _lang = _detect_code(content)
        commands = _detect_commands(content)

        if category in ("python", "ai", "frontend") and code:
            theme = CODE_THEMES[category]
            img = _render_code_editor(topic, code, theme)
        elif category == "sysadmin" and (commands or code):
            img = _render_terminal(topic, commands or code.split("\n"))
        elif category in ("python", "ai", "frontend"):
            synthetic = _build_synthetic_snippet(content, category)
            theme = CODE_THEMES[category]
            img = _render_code_editor(topic, synthetic, theme)
        elif category == "sysadmin":
            # No commands found: still terminal but with a quote-like single line
            hook = _key_sentence(content)
            img = _render_terminal(topic, [f"echo '{hook[:80]}'"])
        else:
            # project / career → editorial
            hook = _key_sentence(content)
            img = _render_editorial(topic, hook, category)

        img.convert("RGB").save(output_path, "PNG", optimize=True)
        logger.info("post image generated: %s (%s bytes)", output_path, output_path.stat().st_size)
        return output_path
    except Exception as e:  # noqa: BLE001
        logger.exception("generate_post_image failed for post %s: %s", post_id, e)
        return None


def _build_synthetic_snippet(content: str, category: str) -> str:
    """When the post has no fenced code, synthesize a short snippet from key
    sentences so the editor template still feels alive."""
    sentences = [
        s.strip() for s in re.split(r"(?<=[.!?])\s+", content) if 30 <= len(s) <= 110
    ][:5]
    comment_prefix = "# " if category in ("python", "ai") else "// "
    lines = []
    for s in sentences:
        for chunk in textwrap.wrap(s, width=68):
            lines.append(f"{comment_prefix}{chunk}")
    if category in ("python", "ai"):
        lines.append("")
        lines.append("def insight() -> dict:")
        lines.append("    return {")
        lines.append('        "stack": ["FastAPI", "React", "Docker"],')
        lines.append('        "ai": ["Ollama", "Claude", "Whisper"],')
        lines.append('        "ready": True,')
        lines.append("    }")
    else:
        lines.append("")
        lines.append("function ship(): Product {")
        lines.append("  return new Product({")
        lines.append('    stack: ["React 19", "Vite", "Tailwind"],')
        lines.append("    deployed: true,")
        lines.append("  });")
        lines.append("}")
    return "\n".join(lines[:12])
