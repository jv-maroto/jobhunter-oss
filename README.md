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

```bash
# 1. Clone
git clone https://github.com/YOUR_HANDLE/jobhunter.git
cd jobhunter

# 2. Backend
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env           # then edit .env and add your ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000

# 3. Frontend (in a separate terminal)
cd frontend
npm install
cp .env.local.example .env.local
npm run dev                    # opens http://localhost:3000
```

Open `http://localhost:3000`, go to **Settings**, and paste your CV data
(`backend/app/data/cv_master.json` has a starter template).

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

### Scrapers
By default the system scrapes for full-stack and sysadmin/devops roles in
Spain via jobspy. To customize:
- Edit `backend/app/scrapers/jobspy_scraper.py:SEARCH_QUERIES` for dev queries
- Edit `backend/app/scrapers/sysadmin_scraper.py:SYSADMIN_QUERIES` for ops queries
- Edit `backend/app/scrapers/hacker_news.py:TECH_KEYWORDS` to filter trending news

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
