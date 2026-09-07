"""Application settings, read from environment with sensible local defaults."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Job Scam Detection API"
    version: str = "0.1.0"

    # Database. SQLite locally so the project runs with no services installed.
    # Set DATABASE_URL to a Postgres URL in deployment.
    database_url: str = f"sqlite:///{ROOT / 'jobscam.db'}"

    # Model artefacts. When absent the service falls back to the stub
    # classifier so the whole pipeline still runs end to end.
    model_path: Path = ROOT / "artifacts" / "model.pkl"
    vectorizer_path: Path = ROOT / "artifacts" / "vectorizer.pkl"

    # Registry seed data.
    company_registry_csv: Path = ROOT / "data" / "external" / "company_registry.csv"
    agency_registry_csv: Path = ROOT / "data" / "external" / "agency_registry.csv"
    blacklist_csv: Path = ROOT / "data" / "external" / "blacklist.csv"

    # Decision thresholds. Tunable without retraining, which is the whole
    # point of keeping the model binary and the tiers separate.
    high_risk_threshold: float = 0.70
    suspicious_threshold: float = 0.35

    # Fuzzy matching. Above the impersonation floor but below an exact match
    # is treated as possible impersonation, not as a verified entity.
    fuzzy_match_threshold: float = 0.90
    impersonation_threshold: float = 0.75

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
