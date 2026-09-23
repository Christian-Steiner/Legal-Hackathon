# Regulatory Change Monitor for LEXR

Legal Hackathon 2026, **Track 3**. Tracks Swiss federal regulatory changes (Fedlex), works out which
client companies and **which of their departments** are affected, drafts a plain-language alert with
citations, and lets a **LEXR lawyer approve, edit or reject every alert** before a client sees it.
Everything is audit-logged. This is not legal advice.

## Quick start (no API keys needed)
Needs [uv](https://docs.astral.sh/uv/) and Node 20+.
```bash
make dev        # installs what's missing, seeds the DB on first run, starts API + UI (Ctrl+C stops both)
```
Open http://localhost:5173. `make reset` gives you a fresh demo DB, and `make help` lists all targets.

Manual steps, if you prefer:
```bash
# backend (Python 3.11+, uv)
cd backend
cp .env.example .env                              # defaults: LLM_PROVIDER=mock, DEMO_MODE=true
uv sync
uv run python -m scripts.seed --pipeline          # 4 demo companies + cached Fedlex + dataset → drafts
uv run uvicorn app.main:app --reload --port 8000  # API docs: http://localhost:8000/docs

# frontend (Node 20+)
cd frontend
npm install
npm run dev                                       # http://localhost:5173
```
Use the "Viewing as" switcher (top right) to change between **LEXR lawyer** and each **client**.

Or run it all in Docker: `docker compose up --build`, then open http://localhost:8010.

## Using a real LLM
Put a key in `backend/.env`:
- `LLM_PROVIDER=apertus` + `APERTUS_API_KEY`: Swisscom **Apertus 1.5 70B**, hosted in Switzerland (key from https://keymaker.ai-weeks.ch/)
- `LLM_PROVIDER=openai` + `OPENAI_API_KEY` (hackathon credits)

Then re-run `uv run python -m scripts.seed --pipeline`.

## How it works
1. **Onboarding**: the client describes its company, activities, legal situation, topics and departments (each department says which functions it covers).
2. **Ingest**: Fedlex SPARQL (new AS publications, upcoming entry into force, open consultations) plus the organisers' xlsx (marked *simulated*). The same change reported twice is merged into one update (dedup by ELI).
3. **Classify**: topics, functional teams, triggered activity flags, urgency (independent of any company).
4. **Match**: transparent rules first, then the LLM decides and must give a reason. Non-matches are stored too.
5. **Draft**: summary, affected departments, next steps, urgency, and citations (ELI + article) for every claim.
6. **Lawyer review**: draft next to the original source text and the matching reasons; approve, edit, reject or request a revision (the model re-drafts with the comment). Approval is enforced in the backend.
7. **Alert**: client inbox grouped by department, "Reviewed by LEXR on …", source links, disclaimer, email preview.
8. **Audit log**: every step, with actor, model and prompt version, and Fedlex source version.

Evaluation against the jury's routing: `uv run python -m scripts.evaluate` (mock baseline: 0.66 mean Jaccard).

## Repo layout
```
backend/app/schemas.py      ← THE contract (mirrored in frontend/src/types.ts)
backend/app/ingest/         Fedlex SPARQL + organisers' dataset
backend/app/ai/             llm client, prompts, rules, classify, matching, drafting (pure functions)
backend/app/services/       pipeline orchestration, review + approval gate
backend/app/routers/        FastAPI endpoints
backend/data/               fedlex_cache.json (demo mode), seed companies, Dataset_Legal.xlsx
backend/scripts/            seed, fetch_fedlex_cache, evaluate
frontend/src/pages/         Dashboard, ReviewQueue, ReviewDetail, Updates, AuditLog, Onboarding, Inbox, Limitations
docs/                       ROADMAP (plan + tasks), CONTRACTS, DEPLOY
```

Team workflow and rules for AI assistants: [CLAUDE.md](CLAUDE.md) · plan: [docs/ROADMAP.md](docs/ROADMAP.md)
