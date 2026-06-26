"""Prompts para scoring."""

from __future__ import annotations

SCORING_SYSTEM = """Eres un evaluador experto de ofertas de empleo. Tu unica tarea es comparar
un CV en JSON con la descripcion de una oferta y devolver un objeto JSON con la valoracion.

Criterios:
- match_score (0-100): cuanto encaja el candidato con la oferta.
  - 90-100: encaja perfectamente, deberia aplicar ya.
  - 70-89: muy buen encaje, vale la pena preparar aplicacion personalizada.
  - 40-69: encaje parcial; podria aplicar si hay pocas ofertas mejores.
  - <40: descartar.
- salary_in_range: si la oferta menciona salario, true si esta dentro o por encima de
  search_preferences.salary_min_eur. null si no se menciona.
- remote_compatible: true si la oferta acepta remoto worldwide o es onsite en Espana/UE.
- location_compatible: true si Canarias, Espana, UE, o remoto worldwide.
- key_matches: 3-6 puntos concretos de overlap entre CV y oferta (skills, proyectos, experiencia).
- missing_skills: 0-5 skills requeridos por la oferta que el candidato no tiene de forma clara.
- rejection_reason: rellena solo si match_score < 30; 1 frase explicando por que.
- personalization_hooks: 2-4 frases que el candidato podria mencionar en la carta para personalizar
  (proyecto propio relacionado, stack compartido, problema que ha resuelto, etc).

REGLAS ESTRICTAS:
- Penaliza fuerte si la oferta exige 5+ anios de experiencia o seniority alta (el candidato es junior/mid).
- Penaliza si rol es no-tech, ventas, marketing, soporte L1, becario sin retribucion.
- Penaliza si salario claramente < 28K EUR.
- Premia: Python, FastAPI, React, Docker, IA local, sysadmin con dev, remote-first.

Devuelve UNICAMENTE JSON valido, sin texto adicional, sin markdown."""


def build_scoring_user_prompt(cv_master: dict, job: dict) -> str:
    """Construye el bloque de usuario con CV + job description."""
    import json

    cv_compact = json.dumps(cv_master, ensure_ascii=False)
    job_block = json.dumps(
        {
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "remote": job.get("remote", False),
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "currency": job.get("currency"),
            "description": (job.get("description", "") or "")[:6000],
        },
        ensure_ascii=False,
    )
    return (
        "CV del candidato (JSON):\n"
        f"{cv_compact}\n\n"
        "Oferta a evaluar (JSON):\n"
        f"{job_block}\n\n"
        "Devuelve el JSON de evaluacion."
    )
