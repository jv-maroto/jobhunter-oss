# Contributing

Thanks for helping! JobHunter is a single-user, local-first tool, so the bar is
simple: **a fresh clone must keep working for everyone**, not just for the author.

## Ground rules

- Nothing personal in the code: no names, cities, salaries, favourite stacks.
  Anything user-specific comes from `backend/app/data/cv_master.json`
  (`search_preferences`, `skills`, …) or from `.env`.
- No fake data in the UI. If a source fails, show the error.
- The API has no auth on purpose (it binds to `127.0.0.1`). Do not add
  deployment files that expose it to the internet.

## Dev setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: py -3.12 -m venv .venv && .venv\Scripts\activate
pip install -e ".[onboarding,dev]"
pytest -q            # tests run against a temp dir, never your real DB/profile
ruff check app tests

cd ../frontend && npm ci && npm run lint && npm run build
cd ../linkedin-ext && npm ci && npm run typecheck && npm run build
```

CI (`.github/workflows/ci.yml`) runs exactly those commands on every PR.

## Adding a job board

1. Add a class in `backend/app/scrapers/` (see `remotive.py` for an API board or
   `tecnoempleo.py` for HTML). Implement `fetch()`; override `configure()` if
   the board needs the user's regions/queries.
2. Register it in `backend/app/scrapers/registry.py:SCRAPER_BY_ID`.
3. Set `scraper_class`, `status: "available"` and `implemented: true` for its
   entry in `backend/app/scrapers/platforms.json`.
4. Add a parser test with a small HTML/JSON fixture in `backend/tests/`.

## Pull requests

- One topic per PR, with a short explanation of *why*.
- Keep the README honest: if a board stops working, mark it as such instead of
  leaving it listed as "working".
