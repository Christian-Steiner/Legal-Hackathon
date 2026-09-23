# One container: FastAPI serves the API and the built React app on port 8000.
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
ENV DATABASE_URL=sqlite:////data/app.db \
    PATH="/app/backend/.venv/bin:$PATH"
VOLUME /data
EXPOSE 8000
CMD ["sh", "-c", "[ -f /data/app.db ] || python -m scripts.seed --pipeline; uvicorn app.main:app --host 0.0.0.0 --port 8000"]
