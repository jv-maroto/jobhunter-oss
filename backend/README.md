# Jobhunter Backend

API REST que scrapea ofertas de empleo, las puntua con Claude Haiku contra el CV del usuario,
genera CVs personalizados + cartas de presentacion con Claude Sonnet, y expone endpoints para el
dashboard frontend y la extension de LinkedIn.

## Stack

- Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite, Pydantic v2
- APScheduler para jobs periodicos (scraping cada 6h, posts semanales)
- httpx + selectolax para scrapers HTTP/HTML
- python-jobspy para LinkedIn/Indeed/Glassdoor
- anthropic SDK (Claude Haiku 4.5 + Sonnet 4.6)
- Typst para compilar CVs a PDF

## Quickstart

```bash
cd jobhunter/backend

# 1. crea venv con uv (recomendado) o pip
uv venv
source .venv/bin/activate
uv pip install -e .

# alternativa con pip puro:
# python3.12 -m venv .venv && source .venv/bin/activate
# pip install -e .

# 2. configura .env
cp .env.example .env
# Edita .env y pon tu ANTHROPIC_API_KEY

# 3. (opcional) instala typst para generar PDFs
brew install typst

# 4. arranca la API
uvicorn app.main:app --reload --port 8000
```

Abre http://localhost:8000/docs para Swagger UI.

## Endpoints principales

```
GET    /jobs                          ?status=&min_score=&source=
GET    /jobs/{id}
PATCH  /jobs/{id}                     # update status / notes
POST   /jobs/{id}/prepare-application # genera CV + cover, devuelve paths
POST   /jobs/scrape-now               # dispara scraping manual

GET    /persons                       ?status=
GET    /persons/{id}
PATCH  /persons/{id}
POST   /persons/{id}/mark-sent

GET    /posts                         ?status=&date=
PATCH  /posts/{id}
POST   /posts/{id}/schedule?when=ISO  # programa publicacion
POST   /posts/generate-week           # genera 7 posts con Sonnet

GET    /metrics/today
GET    /metrics/pipeline
GET    /metrics/companies

GET    /ext/tasks                     # tareas pendientes para extension LinkedIn
POST   /ext/connect-result            # extension reporta resultado
POST   /ext/inbox-messages            # extension envia inbox nuevo
```

## Estructura

```
app/
  main.py            FastAPI app + lifespan + CORS
  config.py          Pydantic Settings
  db.py              SQLAlchemy engine/session/Base
  services.py        load_cv_master, scrape_and_ingest
  scheduler.py       APScheduler (scrape 6h, posts dom 18h, persons lun 06h)
  models/            ORM: Job, Application, Company, Person, Post, ScoreCache
  schemas/           Pydantic v2
  api/               Routers: jobs, persons, posts, metrics, ext
  scrapers/          base + remoteok + remotive + tecnoempleo + jobspy
  scoring/           Claude Haiku + cache local
  ai/                cv_generator, cover_letter, post_generator, connection_message
  data/
    cv_master.json   datos completos del CV (oficial)
    cv_template.typ  plantilla Typst

data/
  applications/{job_id}/ cv.pdf, cv.typ, cover.pdf, cover.txt
  posts/
  cache/
```

## Como funciona el pipeline

1. **Scraping** (`app.services.run_all_scrapers`): ejecuta RemoteOK + Remotive + Tecnoempleo +
   JobSpy en paralelo. Cada scraper devuelve `List[ScrapedJob]` con `hash = md5(title+company+location)`.
2. **Dedup**: por hash en memoria y en DB.
3. **Scoring** (`app.scoring.scorer.score_job`): llama a Haiku con el CV en cache (prompt caching).
   Resultado se guarda en `ScoreCache` para reuso.
4. **Insert**: oferta queda en estado `detected` con su `match_score`.
5. **Prepare application** (manual): `POST /jobs/{id}/prepare-application` llama a Sonnet, genera
   CV adaptado (Typst -> PDF) + carta. Estado pasa a `prepared`.
6. **Pipeline manual**: el dashboard permite mover ofertas a `applied`/`interviewing`/etc via PATCH.

## Scheduler

| Job | Cuando | Que hace |
|-----|--------|----------|
| `scrape_all` | cada 6h | Scrapea + dedup + score |
| `persons_weekly` | lunes 06:00 | Genera 20 personas (placeholders por ahora) |
| `posts_weekly` | domingo 18:00 | Genera 7 posts LinkedIn para la semana |

Desactivable con `ENABLE_SCHEDULER=false`.

## Costes API

- Scoring con Haiku 4.5 + prompt caching: ~0.001 EUR por oferta nueva.
- Generacion CV+cover con Sonnet: ~0.05 EUR por aplicacion preparada.
- Posts semanales: ~0.10 EUR por semana.

Total estimado: ~20 EUR/mes con 200 ofertas scrapeadas/dia.

## Estado actual de los modulos

| Modulo | Estado |
|--------|--------|
| ORM + DB + migraciones | Funcional (SQLAlchemy 2.0, create_all en startup) |
| API REST | Funcional (jobs, persons, posts, metrics, ext) |
| Scraper RemoteOK | Funcional (API publica JSON) |
| Scraper Remotive | Funcional (API publica JSON) |
| Scraper Tecnoempleo | Funcional (HTML, selectores defensivos; puede requerir tuning) |
| Scraper JobSpy | Funcional con python-jobspy instalado |
| Scoring Haiku | Funcional con API key; fallback heuristico sin ella |
| Generador CV Sonnet | Funcional; requiere `typst` en PATH para PDF |
| Generador carta | Funcional |
| Generador posts | Funcional |
| Mensaje de conexion | Funcional |
| Scheduler APScheduler | Funcional |
| Cache de scoring | Funcional (sqlite via ScoreCache) |

## Proximos pasos sugeridos

1. Anadir migraciones Alembic en lugar de `create_all`.
2. Tests de pytest para scoring y scrapers.
3. Image generation real para posts (matplotlib + captura DOM).
4. Persistir API cost en DB para metrics.api_cost_eur.
5. Scraper LinkedIn real via la extension MV3 (cuando se construya).
6. Migrar a Postgres + pgvector cuando haya >5k ofertas (incluir docker-compose).
