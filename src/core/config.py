"""Application settings, read from environment with sensible local defaults."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

    # Browser origins allowed to call the API, comma separated. In deployment
    # set CORS_ORIGINS to the deployed frontend URLs. Held as a string rather
    # than a list because deployment dashboards make plain text easy to paste
    # and JSON quoting easy to get wrong.
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, value: str) -> str:
        """Accept the postgres:// scheme some hosts hand out.

        Render and Heroku expose connection strings beginning postgres://,
        which SQLAlchemy 2.0 no longer recognises. Rewriting it here means the
        value copied from the dashboard works unedited.
        """
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql://", 1)
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        """Allowed origins, parsed from the comma separated setting."""
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


@lru_cache
def get_settings() -> Settings:
    return Settings()
