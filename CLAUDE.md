# CLAUDE.md: rules for every Claude working in this repo

Hackathon project (LEXR Track 3: Regulatory Change Monitor). Three people work in parallel,
each with their own Claude. Read `docs/ROADMAP.md` for the plan and your workstream's tasks.

## Stack
- Backend: Python 3.11+, FastAPI, SQLAlchemy 2 + SQLite, managed with `uv` (in `backend/`)
- Frontend: React 18 + Vite + TypeScript, plain CSS (in `frontend/`)
- LLM: `backend/app/ai/llm.py`, providers `mock` (default, no key), `apertus` (Swisscom), `openai`

## Commands
```bash
make dev      # from repo root: install deps, seed if no DB, run backend :8000 + frontend :5173
make reset    # wipe + re-seed DB;  make test  # pytest + frontend build;  make eval

cd backend && uv sync && uv run python -m scripts.seed --pipeline   # reset DB + seed + run pipeline (mock)
cd backend && uv run uvicorn app.main:app --reload --port 8000     # API on :8000, docs at /docs
cd backend && uv run pytest -q                                      # smoke test (must stay green)
cd backend && uv run python -m scripts.evaluate                     # routing agreement vs jury columns
cd frontend && npm install && npm run dev                           # UI on :5173 (proxies /api to :8000)
cd frontend && npm run build                                        # type-check + build
```

## Ownership: stay in your lane
| Workstream | Owns | Do not edit without asking |
|---|---|---|
| WS1 Data & backend | `backend/app/ingest/`, `services/`, `routers/`, `models.py`, `db.py`, `main.py`, Docker/deploy | `ai/`, `frontend/` |
| WS2 AI & matching | `backend/app/ai/`, `scripts/evaluate.py`, `data/seed_companies.json` | `routers/`, `frontend/` |
| WS3 Frontend | `frontend/src/` | `backend/` |

**Shared contract:** `backend/app/schemas.py` <-> `frontend/src/types.ts`. Changing a shape means updating
both files in the same commit and telling the team. Prefer adding optional fields to renaming or removing them.

## Non-negotiable rules (judging: Responsible AI = 30 %)
1. **No alert without lawyer approval.** Alerts are created only in `services/review.py::_create_alert`,
   called only from `approve()`. Never add another path that creates an `Alert`.
2. **Everything is audited.** Any state change calls `audit.log(...)` in the same transaction.
3. **Citations.** Every factual statement in a draft carries a citation (ELI + article). Drafts without
   citations are flagged in `review.warnings_for` and cannot be approved.
4. **Transparency.** Store and show `model_version` and `prompt_version` on every Match/Draft. Bump the
   `*_VERSION` constant in `ai/prompts.py` when you change a prompt.
5. **Jury columns** (`jury_expected_*` in the xlsx) are evaluation data only. Never feed them into
   rules, prompts or the DB. Only `scripts/evaluate.py` reads them.
6. **Not legal advice.** Never phrase output as a legal conclusion. Keep the disclaimer.
7. **Simulated data** (`is_simulated`) must always be visibly marked in the UI.
8. The app must always run with `LLM_PROVIDER=mock` and `DEMO_MODE=true` (no network, no keys), which
   is our demo safety net.

## Conventions
- AI functions in `app/ai/` are **pure** (dict in, dict out, no DB). DB writes and audit entries happen in `app/services/`.
- `TODO(ws1|ws2|ws3)` marks open work for each workstream. Grep for your tag.
- Keep it simple. This is an MVP due at 15:30. Before pushing: `uv run pytest -q` and `npm run build`.
- Never commit `backend/.env` or API keys.
