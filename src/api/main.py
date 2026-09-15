"""
Application entry point.

Run locally:

    uvicorn src.api.main:app --reload

Interactive docs at http://localhost:8000/docs
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import analyse
from src.api.routes import auth
from src.api.routes import cases
from src.core.config import get_settings
from src.db.models import init_db
from src.models import classifier
from src.verification import registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    registry.load()
    if classifier.is_stub():
        log.warning(
            "Running with the STUB classifier. Results are for pipeline "
            "testing only and must not be presented as model output."
        )
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "Hybrid job posting risk assessment. Content risk and entity "
        "verification are computed independently and reported separately. "
        "Registry data is simulated; this is not an official verification "
        "service."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyse.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(cases.router, prefix="/api")


@app.get("/api/health", tags=["health"])
def health() -> dict:
    """Health probe. Surfaces whether a trained model is actually loaded."""
    return {
        "status": "ok",
        "version": settings.version,
        "model": "stub" if classifier.is_stub() else "trained",
        "thresholds": {
            "high_risk": settings.high_risk_threshold,
            "suspicious": settings.suspicious_threshold,
        },
    }
