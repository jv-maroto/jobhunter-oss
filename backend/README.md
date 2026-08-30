# JobHunter Backend

API REST que scrapea ofertas de empleo, las puntúa contra el perfil del usuario
con el LLM que elija (Anthropic / OpenAI / Gemini / Ollama local), genera CVs
personalizados + cartas de presentación, y expone endpoints para el dashboard y
la extensión de Chrome.

## Stack

- Python **3.12** (solo; `python-jobspy` pinea `numpy`/`regex` sin wheels para 3.13+)
- FastAPI, SQLAlchemy 2.0, SQLite, Pydantic v2
- APScheduler para jobs periódicos (scraping cada 6 h, posts semanales, sync Gmail)
- httpx + selectolax para scrapers HTTP/HTML; python-jobspy para LinkedIn/Indeed
- Router LLM multi-proveedor con fallback (`app/ai/router.py`)
- Typst para compilar CVs a PDF (opcional)

## Quickstart

```bash
cd backend
python3.12 -m venv .venv              # Windows: py -3.12 -m venv .venv
source .venv/bin/activate             # Windows: .venv\Scripts\activate
pip install -e ".[onboarding]"        # onboarding = parsing de CV (PDF/DOCX)

cp .env.example .env                  # opcional: todo tiene valor por defecto
uvicorn app.main:app --reload --reload-include "*.json" --port 8000
```

Abre http://localhost:8000/docs para el Swagger UI. Arranca siempre desde
`backend/` (las rutas de `.env` son relativas a ese directorio).

Typst (para PDFs): `brew install typst` · `winget install --id Typst.Typst` ·
Linux: binario de las releases o `cargo install typst-cli`. Sin Typst se genera
igualmente el `.typ`.

## Endpoints principales

```
GET    /health
GET    /onboarding/status              # {onboarded: bool} -> dispara el wizard
POST   /onboarding/{github|cv|linkedin|merge|complete|reset|roles}

GET    /jobs                           ?status=&min_score=&source=&track=
GET    /jobs/{id}   PATCH /jobs/{id}
POST   /jobs/{id}/prepare-application  # CV + carta
POST   /jobs/scrape-now                # asincrono; 409 si no hay onboarding
GET    /jobs/scrape-status
GET    /jobs/swipe

GET    /settings/cv_master   PUT /settings/cv_master
GET    /settings/search-profile   PUT /settings/search-profile
GET    /settings/platforms/catalog
GET    /settings/ai   PUT /settings/ai   POST /settings/ai/test
GET    /settings/features
POST   /scrape/run                     # sincrono; 409 si no hay onboarding

GET    /persons   PATCH /persons/{id}   POST /persons/{id}/mark-sent
GET    /posts     PATCH /posts/{id}     POST /posts/generate-week
GET    /metrics/today | /metrics/pipeline | /metrics/companies | /metrics/api-costs
GET    /networking/people   POST /networking/people
GET    /comments/suggestions   POST /comments/feed-posts
GET    /integrations/gmail/status   POST /integrations/gmail/{connect|sync|disconnect}
GET    /email-events

GET    /ext/tasks   GET /ext/profile   GET /ext/apply-queue
POST   /ext/connect-result | /ext/inbox-messages | /ext/post-result | /ext/applied | /ext/answer-question
```

## Estructura

```
app/
  main.py            FastAPI app + lifespan + CORS + bootstrap de cv_master.json
  config.py          Pydantic Settings (.env)
  db.py              SQLAlchemy engine/session + mini-migrador
  services.py        load_cv_master, run_all_scrapers, scrape_and_ingest
  scheduler.py       APScheduler (scrape cada N h, posts dom 18:00, gmail)
  models/            ORM
  schemas/           Pydantic v2
  api/               Routers (jobs, onboarding, search_profile, ai_settings, ...)
  scrapers/          registry + platforms.json + un modulo por board
  scoring/           prompts (derivados del perfil) + scorer + track_detector
  ai/                router multi-proveedor, keystore, cv/cover/post generators
  onboarding/        deteccion de primer uso, parsers de CV/LinkedIn/GitHub, fusion
  integrations/gmail/
  data/
    cv_master.example.json   plantilla (se copia a cv_master.json, gitignoreado)
    cv_template.typ          plantilla Typst
tests/               pytest (usa un directorio temporal, nunca tu DB/perfil)
data/                runtime del usuario (gitignoreado)
```

## Pipeline

1. **Onboarding**: hasta que `is_onboarded()` no es `True` (perfil con nombre real
   o marcador `data/.onboarded`), NO se scrapea: ni el scheduler ni "buscar ahora".
2. **Scraping** (`services.run_all_scrapers`): `registry.build_active_scrapers`
   elige los boards según `search_preferences` (regiones + plataformas) y las
   queries salen de `query_builder` (roles + skills del perfil).
3. **Dedup** por hash `md5(title+company+location)` en memoria y en DB.
4. **Scoring** (`scoring/scorer.py`): system prompt construido por
   `build_scoring_system(cv)` con salario mínimo, regiones, seniority, stack,
   idiomas y exclusiones del perfil. Sin LLM → heurística por solapamiento de
   skills. Cache en `ScoreCache`. Tope `MAX_SCORED_JOBS_PER_RUN` por ciclo.
5. **Prepare application**: CV adaptado (Typst → PDF) + carta.
6. **Pipeline manual** vía PATCH / Kanban; opcionalmente Gmail mueve estados.

## Scheduler

| Job | Cuándo | Qué hace |
|-----|--------|----------|
| `scrape_all` | cada `SCRAPE_INTERVAL_HOURS` (6) | scrape + dedup + score (si hay onboarding) |
| `posts_weekly` | domingo 18:00 (`SCHEDULER_TIMEZONE`) | 7 posts en `CONTENT_LANGUAGE` |
| `gmail_sync` | cada `GMAIL_SYNC_INTERVAL_MINUTES` | solo si `ENABLE_GMAIL_TRACKING=true` |

`ENABLE_SCHEDULER=false` lo apaga.

## Tests

```bash
pip install -e ".[onboarding,dev]"
pytest -q
ruff check app tests
```

## Seguridad

La API no tiene autenticación: está pensada para `127.0.0.1` con un único
usuario. No la expongas a internet (el `Dockerfile` es para uso local).
