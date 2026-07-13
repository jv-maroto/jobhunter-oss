# JobHunter

Self-hosted, AI-powered job search command center for solo job seekers.
Scrapes job boards, scores offers against your CV with Claude, prepares
personalized CVs and cover letters, and ships a LinkedIn helper that drafts
posts and comments in your voice — all running on your own machine.

> **Single-user, local-first**: no login, no cloud database, no telemetry.
> Each instance lives on your laptop with your own SQLite DB and your own
> API key. Nothing about you ever leaves your machine except the LLM API calls
> you choose to make.

---

## What it does

| Area | Feature |
|---|---|
| **Discovery** | Scrapes LinkedIn, Indeed, Glassdoor, Remotive, Tecnoempleo (via [jobspy](https://github.com/Bunsly/JobSpy)). Hourly auto-scrape + manual button. |
| **Scoring** | Each new job is scored against your `cv_master.json` by Claude Haiku — match %, missing skills, salary fit, remote compatibility. |
| **Tracks** | Jobs auto-classified into `dev` vs `sysadmin` so you can pursue both with separate Kanbans and salary heuristics. |
| **CV / cover** | One-click "Prepare application" calls Claude Sonnet to write a tailored CV (Typst → PDF) and a cover letter for each job. |
| **LinkedIn helper** | Generates weekly content posts (devlog + trending news from Hacker News) with custom infographics rendered by Playwright. Drafts comments on posts you visit. |
| **Chrome extension** | Auto-fills application forms across Wellfound, Lever, Greenhouse, Ashby, Workable, Indeed and 15+ ATS platforms using your `cv_master.json` data. |

## Quick start

Requires **Python 3.12–3.14** and **Node 20+**.

```bash
# 1. Clone
git clone https://github.com/jv-maroto/jobhunter-oss.git
cd jobhunter-oss

# 2. Backend
cd backend
python3.12 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -e ".[onboarding]"      # the extra adds CV parsing (PDF/DOCX)
cp .env.example .env                # optional: add an LLM key (see below)
uvicorn app.main:app --reload --reload-include "*.json" --port 8000

# 3. Frontend (in a separate terminal)
cd frontend
npm install
cp .env.local.example .env.local     # optional; defaults to localhost:8000
npm run dev                          # http://localhost:3000
```

Open `http://localhost:3000`. On a fresh install the **onboarding wizard**
launches automatically: it builds your profile from your CV (PDF/DOCX), your
GitHub and/or your LinkedIn export, lets you pick countries and job boards, and
writes `backend/app/data/cv_master.json`.

> **Your profile never leaves your machine.** `cv_master.json` is gitignored —
> the repo only ships `cv_master.example.json`, which is copied on first run.
> You can re-run the wizard any time from **Settings → Rehacer onboarding**
> (your current profile is backed up first).

### Do I need an API key?

No. In the wizard's first step you can choose:

- **Local AI (free)** — [Ollama](https://ollama.com) running on your machine.
- **Cloud AI** — Anthropic / OpenAI / Gemini. Paste the key in the wizard or set
  it in `.env`.
- **No AI** — scraping and the Kanban still work; scoring and CV generation don't.

### Optional: Chrome extension

```bash
cd linkedin-ext
npm install
npm run build
```

Then in Chrome → `chrome://extensions` → enable Developer mode → "Load
unpacked" → select the `linkedin-ext/dist/` folder.

---

## Stack

- **Backend**: FastAPI · SQLAlchemy 2.0 · SQLite · APScheduler · httpx
- **Frontend**: Next.js 16 · React 19 · TanStack Query · Tailwind v4 · shadcn/ui
- **AI**: Anthropic Claude Haiku/Sonnet (default) · Gemini fallback · local Ollama support
- **CV/PDF**: Typst (must be installed: `brew install typst` or [typst.app](https://typst.app))
- **Image generation**: Playwright (Chromium headless) for LinkedIn post images
- **Extension**: Chrome MV3 · esbuild · TypeScript

---

## Feature flags

If you only want the job-search core without LinkedIn posting/commenting,
flip these in your `.env`:

```env
ENABLE_POST_GENERATION=false
ENABLE_IMAGE_GENERATION=false
ENABLE_COMMENT_SUGGESTIONS=false
ENABLE_TRENDING_NEWS=false
```

The features stay in the code but the UI hides them.

---

## Configuration tips

### Your CV
Edit `backend/app/data/cv_master.json`. Schema is flexible — add any extra
fields you want; CV / cover letter generation will pick them up.

Key sections:
- `personal` — name, email, phone, links (used by Chrome extension auto-fill)
- `summary_es` / `summary_en` — short professional summary
- `experience` — array of past roles with measurable highlights
- `skills` — grouped by category
- `search_preferences` — salary range, remote/onsite, country preferences
- `narratives` (optional) — long-form answers for common application questions
  (`experience`, `frontend_showcase`, `backend_showcase`, `production_system_story`,
  `cover_letter`). The Chrome extension auto-fills these into textareas.

### Job boards

You pick countries and boards in the wizard (or later in **Settings → Search**).
Search queries are derived from your own roles and skills — nothing is hardcoded
to one person's profile.

**Working today (12):**

| Board | Coverage | Needs a key? |
|---|---|---|
| LinkedIn, Indeed, Glassdoor, Google Jobs | EU + remote (via [jobspy](https://github.com/Bunsly/JobSpy)) | no |
| Remotive, We Work Remotely | remote | no |
| **HN "Who is hiring"** | remote (monthly thread, Algolia API) | no |
| **Arbeitnow** | DE/AT/NL + remote | no |
| Tecnoempleo | ES | no |
| Platsbanken | SE | no |
| **Adzuna** | ES, GB, DE, FR, NL, IT, PT, SE… | yes — **free** at [developer.adzuna.com](https://developer.adzuna.com) |

Adzuna gives the best per-country coverage; set `ADZUNA_APP_ID` / `ADZUNA_APP_KEY`
in `.env`. Without the key it disables itself instead of silently returning nothing.

**Declared but not implemented yet** (StepStone, WTTJ, APEC, Reed, France Travail,
Bundesagentur, TheHub, Nationale Vacaturebank): these show up **greyed out** in the
UI with a "no scraper" badge. They are never silently enabled. PRs welcome — add a
class to `app/scrapers/`, register it in `registry.py:SCRAPER_BY_ID`, and set
`scraper_class` in `platforms.json`.

### Cost control

Every newly scraped job costs one LLM call to score. A wide scrape is easily 400+
jobs, so `MAX_SCORED_JOBS_PER_RUN` (default 150) caps it. Jobs beyond the cap are
still saved — they're just scored on a later run.

### LLM providers
The router supports Anthropic + Gemini + Ollama with automatic fallback.
Set provider order per task tier in `.env`:

```env
LLM_SCORING_TIER=anthropic-haiku,gemini-flash,ollama-qwen
LLM_GENERATION_TIER=anthropic-sonnet,gemini-pro,ollama-qwen
LLM_MESSAGING_TIER=anthropic-haiku,gemini-flash,ollama-qwen
```

If you only have an Anthropic key, only the `anthropic-*` slots will be active.

---

## Privacy

- Your data lives in `backend/jobhunter.db` (SQLite, never uploaded)
- Generated CVs/cover letters in `backend/data/applications/<company-slug>/`
- The only network calls are to:
  - Job boards (jobspy)
  - Hacker News API (trending feature)
  - Whatever LLM provider you configure (Anthropic / Gemini / nobody if you use Ollama)
- The Chrome extension only auto-fills forms when you click its button — no background data collection

---

## License

MIT.

## Credits

Built originally to scratch one engineer's own job-search itch. Now open
sourced so other devs running their own search can skip rebuilding the
plumbing. PRs welcome.
