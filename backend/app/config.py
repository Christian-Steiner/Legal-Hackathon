"""Runtime configuration, read from environment variables / backend/.env."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # Demo mode: Fedlex ingest reads data/fedlex_cache.json instead of calling the live endpoint.
    demo_mode: bool = True
    database_url: str = f"sqlite:///{DATA_DIR / 'app.db'}"

    # LLM provider: "mock" (no key, deterministic heuristics), "apertus" (Swisscom, Swiss-hosted),
    # or "openai". Apertus and OpenAI both go through the OpenAI-compatible client.
    llm_provider: str = "mock"
    llm_temperature: float = 0.1
    # Parallel LLM calls in the pipeline (Apertus allows 5 req/s; each call takes several seconds).
    llm_concurrency: int = 6
    # Hard cap on requests per second across all threads (Apertus limit: 5 req/s -> stay below).
    llm_max_rps: float = 3.0
    # Reuse earlier answers for identical prompts (data/llm_cache/). Makes repeated resets ~instant.
    llm_cache: bool = True

    apertus_api_key: str = ""
    apertus_base_url: str = "https://api.swisscom.com/products/swiss-ai-weeks/apertus-1.5-70b/v1"
    apertus_model: str = "swiss-ai/Apertus-v1.5-70B"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"

    # Optional: Supertext translation of source texts for the reviewer (TODO workstream 2)
    supertext_api_key: str = ""

    fedlex_endpoint: str = "https://fedlex.data.admin.ch/sparqlendpoint"
    fedlex_cache_file: Path = DATA_DIR / "fedlex_cache.json"
    dataset_file: Path = DATA_DIR / "Dataset_Legal.xlsx"

    # Serve the built frontend (frontend/dist) from FastAPI - used in the Docker image.
    frontend_dist: Path = BACKEND_DIR.parent / "frontend" / "dist"


settings = Settings()
