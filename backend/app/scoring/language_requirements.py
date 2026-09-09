from __future__ import annotations

import re
import unicodedata
from typing import Any

_ALIASES = {
    "german": ("german", "deutsch", "aleman", "allemand"),
    "english": ("english", "ingles", "anglais", "englisch"),
    "french": ("french", "francais", "frances", "franzosisch"),
    "italian": ("italian", "italiano", "italien"),
    "spanish": ("spanish", "espanol", "espagnol", "spanisch"),
}
_LEVELS = {"a1": 1, "a2": 2, "b1": 3, "b2": 4, "c1": 5, "c2": 6}
_PREFERRED = r"\b(?:optional|preferred|advantageous|a plus|nice[- ]to[- ]have|ideally|von vorteil|wunschenswert|un atout|apprecie|deseable|preferible)\b"
_REQUIRED = r"\b(?:required|mandatory|must|essential|necessary|requirement|erforderlich|voraussetzung|zwingend|obligatoire|requis|exige|obligatorio|imprescindible)\b"
_NEGATED = r"\b(?:not (?:\w+ ){0,2}(?:required|necessary|essential|mandatory)|no .{0,35}(?:required|necessary)|nicht (?:\w+ ){0,2}(?:erforderlich|notwendig)|keine? .{0,35}(?:erforderlich|notwendig)|pas (?:\w+ ){0,2}(?:requis|obligatoire)|no (?:es )?(?:obligatorio|necesario)|not a (?:requirement|prerequisite))\b"
_WORKING = r"\b(?:professional|working proficiency|proficient|sehr gute?|gute?|sichere?|fliessende?|verhandlungssichere?)\b"


def _norm(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    ).lower()


def _rank(level: str) -> int | None:
    ranks = [_LEVELS[m.group()] for m in re.finditer(r"\b(?:a1|a2|b1|b2|c1|c2)\b", level)]
    if ranks:
        return max(ranks)
    if re.search(r"\b(?:native|nativo|maternal|mother tongue|muttersprache)\b", level):
        return 6
    if re.search(r"\b(?:fluent|fluido|courant)\b", level) and not re.search(r"\bnot\b", level):
        return 5
    if re.search(_WORKING, level):
        return 4
    if re.search(r"\b(?:intermediate|intermedio)\b", level):
        return 3
    if re.search(r"\b(?:basic|beginner|elementary|principiante|grundkenntnisse)\b", level):
        return 1
    if re.search(r"\b(?:none|no proficiency)\b", level):
        return 0
    return None


def _clauses(sentence: str, language_pattern: str) -> list[str]:
    clauses = []
    for part in re.split(r",|\b(?:but|while|whereas|however|mais|aber|pero)\b", sentence, flags=re.I):
        start = 0
        for separator in re.finditer(r"\b(?:and|und|et|y)\b", part, flags=re.I):
            left = _norm(part[start:separator.start()])
            right = _norm(part[separator.end():])
            languages = list(re.finditer(language_pattern, left))
            if languages and re.search(language_pattern, right) and re.search(
                _REQUIRED + "|" + _PREFERRED, left[languages[-1].end():],
            ):
                clauses.append(part[start:separator.start()].strip())
                start = separator.end()
        clauses.append(part[start:].strip())
    return clauses


def language_checks(job: dict[str, Any], cv: dict) -> list[dict[str, Any]]:
    """Return exact posting excerpts; absent or ungraded profile evidence is unknown."""
    aliases = dict(_ALIASES)
    candidate = {}
    for entry in cv.get("languages") or []:
        if not isinstance(entry, dict):
            continue
        name = _norm(str(entry.get("name") or "")).strip()
        if not name:
            continue
        language = next((key for key, names in aliases.items() if name in names), name)
        aliases.setdefault(language, (name,))
        level = str(entry.get("level") or "").strip()
        candidate[language] = (_rank(_norm(level)), f"{language.title()}: {level}" if level else None)

    names = {name: language for language, names in aliases.items() for name in names}
    description = str(job.get("description") or "")
    for mention in re.finditer(
        r"\b(?i:fluent|native)(?: (?i:proficiency|speaker|in|of))*[: (),-]*([A-Z][^\W\d_]+)\b"
        r"|\b([A-Z][^\W\d_]+)(?: (?i:language|proficiency|level|at))*[: (),-]*(?i:a1|a2|b1|b2|c1|c2)\b",
        description,
    ):
        name = _norm(mention.group(1) or mention.group(2))
        if name not in {"python", "java", "javascript", "typescript", "sql", "rust", "go", "programming", "communication", "written", "spoken"}:
            names.setdefault(name, name)
    pattern = r"\b(?:" + "|".join(re.escape(name) for name in names) + r")(?:kenntnisse)?\b"
    checks = []
    # ponytail: explicit clause rules; use reviewed extraction for ambiguous prose.
    for sentence in re.split(r"[\n.!?;]", description):
        for excerpt in _clauses(sentence, pattern):
            text = _norm(excerpt)
            mentions = list(re.finditer(pattern, text))
            if not mentions or re.search(_NEGATED, text):
                continue
            preferred = bool(re.search(_PREFERRED, text))
            required = bool(re.search(_REQUIRED, text))
            shared_rank = _rank(text)
            if not preferred and not required and shared_rank is None:
                continue
            for i, mention in enumerate(mentions):
                language = names[mention.group().removesuffix("kenntnisse")]
                before = text[mentions[i - 1].end() if i else 0:mention.start()]
                after = text[mention.end():mentions[i + 1].start() if i + 1 < len(mentions) else len(text)]
                suffix = re.match(r"(?: language)?(?: proficiency)?(?: level)?(?: at)?[: (),-]*(a1|a2|b1|b2|c1|c2|fluent|native)\b", after)
                prefix = re.search(r"\b(fluent|native|fluido|courant)(?: (?:proficiency|speaker|in|of))?[: (),-]*$", before)
                rank = _rank(suffix.group(1)) if suffix else (_rank(prefix.group(1)) if prefix else shared_rank)
                importance = "preferred" if preferred else ("required" if required or rank is not None else "unclear")
                proficiency, evidence = candidate.get(language, (None, None))
                status = "unknown" if proficiency is None or rank is None else ("met" if proficiency >= rank else "gap")
                if rank is None and proficiency is not None and proficiency >= 4 and re.search(r"\bproficiency\s+in\s*$", before):
                    status = "met"
                check = {
                    "kind": "language", "importance": importance, "status": status,
                    "requirement": excerpt, "evidence": evidence,
                }
                if check not in checks:
                    checks.append(check)
    return checks
