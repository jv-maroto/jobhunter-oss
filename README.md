# JobHunter

Self-hosted, AI-assisted job search command center for solo job seekers.
Scrapes job boards, scores offers against **your** CV with the LLM of your
choice (Anthropic / OpenAI / Gemini / local Ollama), prepares tailored CVs and
cover letters, and ships a Chrome extension that auto-fills application forms
and helps with LinkedIn — all running on your own machine.

> **Single-user, local-first**: no login, no cloud database, no telemetry.
> Everything lives on your laptop: a SQLite DB, your profile JSON and the API
> keys you choose to add. The only outbound traffic is to the job boards and to
> the LLM provider you pick (none if you use Ollama).

---

## What it does

| Area | Feature |
|---|---|
| **Discovery** | Scrapes LinkedIn, Indeed, Remotive, We Work Remotely, HN "Who is hiring", Arbeitnow, Tecnoempleo, Platsbanken and Adzuna. Auto-scrape every 6 h (configurable) + a "search now" button. |
| **Scoring** | Every new job is scored against your profile: match %, missing skills, salary fit, remote/location compatibility. Rules come from *your* `search_preferences` (salary, countries, seniority, stack), not from a hardcoded persona. |
| **Tracks** | Data engineering, analytics engineering, BI, data analysis, data science, AI/ML and quantitative roles, alongside software and infrastructure. Jobs and swipe show all families by default. |
| **CV / cover** | One-click "Prepare application" uses your configured existing PDF unchanged, or generates a tailored CV, plus a cover letter. Each preparation keeps separate files. |
| **LinkedIn helper** | Weekly content posts (devlog + trending Hacker News) with generated infographics; comment suggestions on posts you visit; connection notes. |
| **Chrome extension** | Auto-fills application forms on Wellfound, Lever, Greenhouse, Ashby, Workable, Indeed and 15+ ATS platforms from your profile data. |
| **Tracking** | Optional read-only Gmail sync classifies recruiter replies and moves jobs through the pipeline (reversible). |

## Quick start

Requires **Python 3.12** (exactly — `python-jobspy` pins `numpy`/`regex` versions that
have no wheels for 3.13/3.14 yet) and **Node 20+**.

```bash
# 1. Clone
git clone https://github.com/jv-maroto/jobhunter-oss.git
cd jobhunter-oss

# 2. Backend
cd backend
python3.12 -m venv .venv                # Windows: py -3.12 -m venv .venv
source .venv/bin/activate               # Windows: .venv\Scripts\activate
pip install -e ".[onboarding]"          # the extra adds CV parsing (PDF/DOCX)
cp .env.example .env                    # optional; every setting has a default
uvicorn app.main:app --reload --reload-include "*.json" --port 8000

# 3. Frontend (separate terminal)
cd frontend
npm install
cp .env.local.example .env.local        # optional; defaults to http://localhost:8000
npm run dev                             # http://localhost:3000
```

Open `http://localhost:3000`. On a fresh install the **onboarding wizard** starts
automatically: pick your AI, build your profile from your CV (PDF/DOCX), your
GitHub and/or your LinkedIn export, choose countries and job boards, and it writes
`backend/app/data/cv_master.json`. **Scraping does not start until the wizard is
done** — without a profile there are no meaningful queries.

> **Your profile is stored locally.** Configured cloud AI providers receive the profile and task content needed for generation or scoring. `cv_master.json` is gitignored —
> the repo only ships `cv_master.example.json`, which is copied on first run.
> Re-run the wizard any time from **Settings → Redo onboarding** (your current
> profile is backed up first).

### Do I need an API key?

No. The wizard's first step lets you choose:

- **Local AI (free)** — [Ollama](https://ollama.com) on your machine. Pull the
  model first: `ollama pull qwen2.5:7b` (change it with `OLLAMA_MODEL` in `.env`).
  The wizard tells you if Ollama is running but the model is missing.
- **Cloud AI** — Anthropic / OpenAI / Gemini. Paste the key in the wizard (stored
  in `backend/data/integrations/ai.json`, never sent to the browser) or set it in `.env`.
- **No AI** — scraping and the Kanban still work. Scoring falls back to an
  explicitly marked heuristic. CVs and cover letters use a factual local fallback;
  PDF generation still requires Typst.

### Use your ChatGPT account through Codex

Install Codex CLI 0.153.4 or newer on the backend machine and run `codex login`
with your ChatGPT account. Choose **OpenAI Codex (ChatGPT account)** in onboarding
or AI settings, save, then test. No OpenAI API key is needed. Requests use your
Codex allowance; task content is sent to OpenAI. This is a local backend option;
the supplied Docker image does not include Codex or your login.

`CODEX_MODEL`, `CODEX_REASONING_EFFORT`, `CODEX_BINARY`, and
`CODEX_TIMEOUT_SECONDS` configure this provider in `backend/.env`. Defaults are
`gpt-6-astra`, `medium`, `codex`, and 180 seconds. Calls run one at a time in an
ephemeral read-only workspace, with shell, web search and user-configured
connectors disabled. Codex mode uses only Codex, with no paid API fallback.
CLI generation does not expose temperature or a strict output-token limit;
the requested length is included in the prompt. API euro estimates do not
represent subscription usage. See [Codex automation](https://learn.chatgpt.com/docs/non-interactive-mode).

### Optional tools

| Tool | Used for | Install |
|---|---|---|
| **Typst** | Compiling the generated CV/cover letter to PDF. Without it you still get the `.typ` source. | macOS `brew install typst` · Windows `winget install --id Typst.Typst` · Linux: binary from [typst releases](https://github.com/typst/typst/releases) or `cargo install typst-cli` |
| **Playwright (Chromium)** | Rendering LinkedIn post images from HTML. Falls back to a Pillow-only image. | `npx playwright install chromium` (needs Node) |

### Optional: Chrome extension

```bash
cd linkedin-ext
npm install
npm run build
```

Then in Chrome → `chrome://extensions` → enable Developer mode → "Load unpacked"
→ select `linkedin-ext/dist/`. Set `CHROME_EXTENSION_ID` in `backend/.env` to
restrict the API's CORS to your extension only (see `.env.example`).

---

## Stack

- **Backend**: FastAPI · SQLAlchemy 2.0 · SQLite · APScheduler · httpx · selectolax
- **Frontend**: Next.js 16 · React 19 · TanStack Query · Tailwind v4 · shadcn-style UI
- **AI**: provider router with automatic fallback — Anthropic, OpenAI, Gemini, Ollama
- **CV/PDF**: Typst · **Post images**: Playwright (Chromium) with Pillow fallback
- **Extension**: Chrome MV3 · esbuild · TypeScript

---

## Configuration

All settings live in `backend/.env` (see `.env.example`; everything has a default).

### Language & schedule

```env
CONTENT_LANGUAGE=es          # language of generated posts/notes: es | en
SCHEDULER_TIMEZONE=Europe/Madrid
SCRAPE_INTERVAL_HOURS=6
ENABLE_SCHEDULER=true
```

The dashboard UI follows your browser language (Spanish → ES, otherwise EN) and
has a toggle.

### Feature flags

Only want the job-search core without the LinkedIn posting/commenting side?

```env
ENABLE_POST_GENERATION=false
ENABLE_IMAGE_GENERATION=false
ENABLE_COMMENT_SUGGESTIONS=false
ENABLE_TRENDING_NEWS=false
```

### Your profile

`backend/app/data/cv_master.json` — edit it from **Settings** or by hand. The
schema is flexible; key sections:

- `personal` — name, email, phone, links (used by the extension's auto-fill)
- `summary_es` / `summary_en`, `experience`, `education`, `skills` (grouped), `languages`
- `search_preferences` — `salary_min`, `salary_max`, `salary_currency`, `regions` / `region_preset`, `remote_only`,
  `roles`, `exclude_keywords`, optional `seniority` (`junior | mid | senior | lead`;
  unspecified if absent). **These drive both the search queries and
  the scoring rules.**
- `search_preferences.employment_types` and `seniority` select contract and career-level targets. An
  unspecified contract stays unconfirmed; full-time does not mean permanent.
- Project `context`, `context_detail`, `role_families` and `claim_boundaries` keep
  academic projects separate from employment and guide tailored document selection.
- `narratives` (optional) — long answers for common application questions that the
  extension pastes into textareas.

### Existing application CVs

To keep a supplied CV unchanged, copy it into `backend/data/resumes/` and configure
`application_documents.mode` as `"existing"` in your local profile. Map each selected
track in `application_documents.cv_by_track` to its `filename`, SHA-256 `sha256`,
and `language: "en"`. Settings shows the role-to-file mapping. Preparation verifies
the file and copies identical bytes; a missing or changed file produces an error
instead of generating a replacement. Original files outside Jobhunter are not edited.
Remove this mode to use the tailored-CV flow.

### Job boards

Pick countries and boards in the wizard or later in **Settings → Search**.
Queries are derived from your roles and skills.

You can also add a job directly from **Jobs**: paste its public URL or enter the
title, company and description manually. Open the job to review the description,
required and preferred qualifications, evidence from your profile and unanswered
questions. Fit scores are estimates; check missing information before applying.

The **Switzerland only** preset searches CH. Every selected role is retained in
automatic queries. LinkedIn, Indeed and Google Jobs support Swiss searches; only
enabled boards run. LinkedIn fetches full descriptions for requirement checks.
Manual and scheduled searches share a status and cannot overlap in one backend process.
Remote jobs need explicit eligibility for a selected country.
EU/EEA-only remote postings do not establish Swiss eligibility. Existing application
history stays available when preferences change.

Salary amounts retain their source currency and pay period. Set a CHF annual range
in Search settings if desired; leave it blank to avoid a salary filter. Comparisons
require the same currency and a stated annual period: the app does not invent FX
rates, working hours, or a market salary from an employer's name. Legacy
`salary_min_eur` / `salary_max_eur` profiles remain readable.

Profile saves validate JSON, keep backups, and invalidate generated-answer caches
through their profile fingerprint. Onboarding can be resumed without discarding
the saved profile. Pending jobs are refreshed against saved profile changes using
clearly labeled heuristic estimates; application history remains intact. Autofill refreshes the profile on every click and leaves
unconfirmed permission, residence and experience claims for manual review.

| Board | Coverage | Needs a key? | Status |
|---|---|---|---|
| LinkedIn, Indeed | EU + remote (via [jobspy](https://github.com/Bunsly/JobSpy)) | no | working |
| Google Jobs | EU + remote (jobspy) | no | off by default |
| Glassdoor | — | no | **off by default**: jobspy currently gets HTTP 400 from Glassdoor for any location |
| Remotive, We Work Remotely | remote | no | working |
| HN "Who is hiring" | remote (monthly thread, Algolia API) | no | working |
| Arbeitnow | DE/AT/NL + remote | no | working |
| Tecnoempleo | ES | no | working (HTML parser, verified 2026-08) |
| Platsbanken | SE | no | working |
| Adzuna | ES, GB, DE, FR, NL, IT, PT, SE… | yes — free at [developer.adzuna.com](https://developer.adzuna.com) | working with `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` |

Declared but **not implemented** (StepStone, WTTJ, APEC, Reed, France Travail,
Bundesagentur, TheHub, Nationale Vacaturebank) show up greyed out in the UI and are
never silently enabled. See [CONTRIBUTING.md](CONTRIBUTING.md) to add one.

### Review applications and follow up

**Applications** is a paginated register of saved jobs, prepared documents and
recorded submissions. Review a prepared application to edit and save its cover
letter, copy its text and open the exact CV and cover PDFs. Unsaved edits stay in
the editor after a save failure; save them before exporting the cover PDF.
Submitted or closed versions are read-only; prepare a new version to change them.

Opening the original job does not record an application. After submitting through
the employer's process, use **I submitted this application**, optionally entering
the actual submission time. Add notes, a next action and its due date on the job;
**Today** lists due follow-ups, and **Applications** can filter by a due date.

### Cost control

Every newly scraped job costs one LLM call to score. `MAX_SCORED_JOBS_PER_RUN`
(default 150) caps it per cycle; jobs beyond the cap are saved unscored and scored
on a later run.

---

## Running with Docker (local only)

```bash
cd backend
docker build -t jobhunter-backend .
docker run --rm -p 127.0.0.1:8000:8000 -v "$PWD/data:/app/data" --env-file .env jobhunter-backend
```

**Do not expose the API to the internet.** It has no authentication by design
(single user on localhost): anyone reaching it could read your profile and spend
your API key.

---

## Privacy

- Your data is stored in `backend/jobhunter.db` (SQLite), `backend/data/`, and the gitignored profile. AI task inputs are sent to the provider you configure; local Ollama keeps that processing local.
- Generated CVs/cover letters in `backend/data/applications/<company-slug>/`.
- Network calls go only to: the job boards you enable, GitHub (onboarding, optional),
  Hacker News (trending posts, optional), Gmail (if you connect it, read-only),
  Google Fonts when rendering post images with Playwright, and the LLM provider you configure.
- The Chrome extension only acts when you click its button; no background data collection.

Keep identity, contact details, career evidence and search preferences in your local
`backend/app/data/cv_master.json`; keep credentials and machine-specific paths in
`backend/.env` or the dashboard's local integration store. These files, the SQLite
database and its sidecars, `backend/data/`, `cvs-out/` exports, `output/`, local
code indexes and runtime logs are ignored. Public examples and test fixtures must
use synthetic data. Preserve upstream author and license attribution.

Before preparing a contribution, run these read-only checks from the repository
root; they do not stage, commit, push or open a PR:

```bash
python3 scripts/test-public-source.py
python3 scripts/check-public-source.py
python3 scripts/check-public-source.py --with-private-values
```

The default check scans tracked files and eligible untracked files, including
symlink targets, for private artifact paths, credential patterns and local home
paths. The optional check also compares identity, contact, employer, institution,
project and credential values from your local profile, `.env` files and integration
store without printing those values. Short names use whole-word matching; shared
company or project names may need review when they also appear in public documentation.
`CV_MASTER_PATH` and `DATA_DIR` in `backend/.env` or the environment select custom
locations. A fresh CI checkout needs no private configuration.

After reviewing and staging only the intended source files, check the complete
index with `python3 scripts/check-public-source.py --staged --with-private-values`.
This reads the staged bytes, including tracked files that now match ignore rules.
A successful check is a useful guard, not proof of anonymity: review the diff,
public binary assets, screenshots and eventual commit metadata separately. The
scanner does not unpack compressed PDF/image content or inspect Git history.
Never attach local exports or runtime logs to a PR without reviewing their contents.

## Development

```bash
cd backend && pip install -e ".[onboarding,dev]" && pytest -q && ruff check app tests
cd frontend && npm run lint && npm run test:unit && npm run build
cd linkedin-ext && npm run typecheck && npm test
```

CI runs the same on every push/PR. Tests use a temporary directory, never your
real DB or profile.

## License

[MIT](LICENSE).

## Credits

Built originally to scratch one engineer's own job-search itch, then made generic
so anyone can clone it and run their own search. PRs welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md).
