# Regulatory Change Monitor - local dev.  `make dev` = install what's missing, seed if needed, start everything.
.PHONY: dev backend frontend setup reset test eval fedlex-cache llm-check try help

BACKEND_PORT  ?= 8000
FRONTEND_PORT ?= 5173

help:
	@echo "make dev       install deps if needed, seed DB if missing, run backend + frontend (Ctrl+C stops both)"
	@echo "make reset     wipe the DB and re-seed (companies + cached Fedlex + dataset + pipeline)"
	@echo "make backend   API only on :$(BACKEND_PORT)      make frontend   UI only on :$(FRONTEND_PORT)"
	@echo "make test      backend smoke test + frontend type-check/build"
	@echo "make eval      routing agreement vs jury columns"
	@echo "make llm-check test the LLM provider/key in backend/.env (1 tiny call)"
	@echo "make try ID=fedlex:oc/2026/322   run ONE update through classify/match/draft with the LLM"
	@echo "make try FILE=data/samples/incoming_update.json   same, for a new incoming update"
	@echo "make fedlex-cache   refresh data/fedlex_cache.json from the live endpoint"

dev: setup backend/data/app.db
	@for p in $(BACKEND_PORT) $(FRONTEND_PORT); do \
	  if lsof -ti tcp:$$p >/dev/null 2>&1; then echo "Port $$p is already in use - stop that process first (lsof -ti tcp:$$p | xargs kill)"; exit 1; fi; \
	done
	@echo "\n  UI:  http://localhost:$(FRONTEND_PORT)\n  API: http://localhost:$(BACKEND_PORT)/docs\n  Ctrl+C stops both.\n"
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --port $(BACKEND_PORT)) & \
	(cd frontend && npm run dev -- --port $(FRONTEND_PORT) --strictPort) & \
	wait

backend: setup backend/data/app.db
	cd backend && uv run uvicorn app.main:app --reload --port $(BACKEND_PORT)

frontend: frontend/node_modules/.installed
	cd frontend && npm run dev -- --port $(FRONTEND_PORT) --strictPort

setup: backend/.env backend/.venv/.synced frontend/node_modules/.installed

backend/.env:
	cp backend/.env.example backend/.env
	@echo "Created backend/.env (LLM_PROVIDER=mock). Add API keys there to use Apertus/OpenAI."

backend/.venv/.synced: backend/pyproject.toml backend/uv.lock
	cd backend && uv sync
	@touch $@

frontend/node_modules/.installed: frontend/package.json frontend/package-lock.json
	cd frontend && npm install
	@touch $@

backend/data/app.db:
	cd backend && uv run python -m scripts.seed --pipeline

reset: setup
	cd backend && uv run python -m scripts.seed --pipeline

test: setup
	cd backend && uv run pytest -q
	cd frontend && npm run build

eval: setup
	cd backend && uv run python -m scripts.evaluate

fedlex-cache: setup
	cd backend && uv run python -m scripts.fetch_fedlex_cache

llm-check: setup
	cd backend && uv run python -m scripts.llm_check

try: setup backend/data/app.db
	cd backend && uv run python -m scripts.process_one $(if $(FILE),--file $(FILE),--id $(or $(ID),dataset:R005))
