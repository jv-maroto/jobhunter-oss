"""Lossless, deterministic compatibility view of multilingual profile data.

No translation, inferred employment, credential equivalence or duration is added.
Original source fields remain authoritative; metadata records fallback provenance
and factual contradictions that need review. This is not a profile migration.
"""
from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from typing import Any

VERSION = 1
_FIELDS = (
    "degree", "qualification", "role", "title", "highlights", "bullets",
    "description", "summary", "responsibilities", "context", "context_detail",
    "claim_boundaries", "name", "domain", "start", "end",
)


def degree_level(value: Any) -> int | None:
    """Recognize explicit labels only; a course is never a degree."""
    text = "".join(c for c in unicodedata.normalize("NFKD", str(value or "").lower())
                   if not unicodedata.combining(c))
    if re.search(r"\b(?:course|curso|coursework|certificate|certificado|scrum master)\b", text):
        return None
    patterns = (
        (5, r"\b(?:ph\.?d\.?|doctorate|doctoral degree|doctorado)\b"),
        (4, r"\b(?:master(?:'s)?|m\.?sc\.?)\b"),
        (3, r"\b(?:bachelor(?:'s)?|b\.?sc\.?|grado universitario|licenciatura)\b"),
        (2, r"\b(?:associate(?:'s)?|vocational diploma|tecnico superior|grado superior|formacion profesional)\b"),
        (1, r"\b(?:high school|secondary school|bachillerato)\b"),
    )
    return next((rank for rank, pattern in patterns if re.search(pattern, text)), None)


def field_variants(entry: dict, field: str) -> list[Any]:
    """Original variants, without claiming translations are semantically equal."""
    return [entry[key] for key in (field, f"{field}_en", f"{field}_es")
            if entry.get(key) not in (None, "", [], {})]


def normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Return a CV-compatible deep copy with canonical fallbacks and metadata.

    Existing canonical values win; otherwise English then Spanish is selected
    solely for reader compatibility. Every original variant remains available.
    Re-normalizing this view is idempotent. No input is mutated.
    """
    result = deepcopy(profile)
    previous = result.pop("_normalization", {})
    provenance = deepcopy(previous.get("provenance", [])) if isinstance(previous, dict) else []
    conflicts: list[dict] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, list):
            for index, entry in enumerate(value):
                visit(entry, f"{path}[{index}]")
        elif isinstance(value, dict):
            for field in _FIELDS:
                if value.get(field) in (None, "", [], {}):
                    for suffix in ("en", "es"):
                        key = f"{field}_{suffix}"
                        if value.get(key) not in (None, "", [], {}):
                            value[field] = deepcopy(value[key])
                            record = {"path": f"{path}.{field}".lstrip("."),
                                      "source_path": f"{path}.{key}".lstrip(".")}
                            if record not in provenance:
                                provenance.append(record)
                            break
            for field in ("start", "end", "degree", "qualification"):
                variants = field_variants(value, field)
                comparable = ({degree_level(v) for v in variants} - {None}
                              if field in {"degree", "qualification"}
                              else {str(v).strip() for v in variants})
                if len(comparable) > 1:
                    conflicts.append({"path": f"{path}.{field}".lstrip("."),
                                      "variants": deepcopy(variants),
                                      "reason": "Conflicting explicit values require review"})
            for key, child in list(value.items()):
                visit(child, f"{path}.{key}".lstrip("."))

    visit(result, "")
    result["_normalization"] = {"version": VERSION, "provenance": provenance, "conflicts": conflicts}
    return result
