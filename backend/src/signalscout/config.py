from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://signalscout:signalscout@localhost:5433/signalscout"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    # Tried in order when a model's (free-tier, per-day) quota runs out
    gemini_fallback_models: str = "gemini-3.1-flash-lite,gemini-flash-lite-latest,gemini-3.6-flash,gemini-3.7-flash,gemini-3.5-flash,gemini-3.8-flash"

    # Cost / politeness controls
    max_extract_per_run: int = 60  # LLM calls per pipeline run
    llm_concurrency: int = 4
    llm_requests_per_minute: int = 12  # free tier allows 15 RPM per model
    enrich_concurrency: int = 8
    enrich_ttl_days: int = 7  # re-crawl a company website at most once a week
    feed_lookback_days: int = 30
    http_timeout: float = 12.0
    user_agent: str = (
        "Mozilla/5.0 (compatible; SignalScoutBot/0.1; +https://github.com/varunseemar/signalscout)"
    )

    cors_origins: str = "http://localhost:3000"

    # Public demo protection: when set, write actions require the X-Admin-Token header
    admin_token: str = ""
    email_drafts_per_hour: int = 5  # per visitor IP, for non-admin visitors

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        # Hosted Postgres (Neon, Render) hands out postgres:// or postgresql:// URLs
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
