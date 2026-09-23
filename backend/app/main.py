from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import schemas
from app.ai import llm
from app.config import settings
from app.db import init_db
from app.routers import companies, drafts, pipeline, updates


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Regulatory Change Monitor (LEXR hackathon)", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

for r in (companies.router, updates.router, drafts.router, pipeline.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta", response_model=schemas.Meta)
def meta():
    return schemas.Meta(demo_mode=settings.demo_mode, llm_provider=settings.llm_provider, llm_model=llm.model_version())


# Production: serve the built React app from the same origin (see Dockerfile).
if settings.frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=settings.frontend_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = settings.frontend_dist / path
        return FileResponse(f if path and f.is_file() else settings.frontend_dist / "index.html")
