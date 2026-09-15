"""
Classifier wrapper.

The contract with modelling is deliberately narrow:

    text (str)  ->  probability (float between 0 and 1)

The model does not see registry data, does not know about blacklists, and
does not assign a risk tier. Those belong to later stages. Keeping the
boundary here means modelling can iterate freely without touching the API,
and the API can be built before the model exists.

The trained artefact is a single sklearn Pipeline that accepts raw text and
performs its own vectorising and feature construction internally. An earlier
revision exported a separate vectoriser; that file is still loaded if present
so older artefacts keep working, but it is no longer required.
"""

from __future__ import annotations

import logging
import re

from src.core.config import get_settings
from src.core.schemas import ModelResult

log = logging.getLogger(__name__)

# Loaded once at import, reused across requests.
_model = None
_vectorizer = None
_loaded = False
_version = "stub-0.1"


def _load() -> None:
    """Attempt to load the trained artefacts, falling back to the stub.

    A missing model is a normal state during development, not an error. The
    service starts either way so frontend work is never blocked on modelling.
    """
    global _model, _vectorizer, _loaded, _version

    if _loaded:
        return
    _loaded = True

    settings = get_settings()

    if not settings.model_path.exists():
        log.warning(
            "Model artefact not found at %s. Using stub classifier.",
            settings.model_path,
        )
        return

    try:
        import joblib

        # Importing the transformer registers it under its real module path.
        # joblib stores a class by import path rather than by value, so the
        # pipeline cannot be reconstructed unless this module is importable.
        try:
            from src.models import feature_builder  # noqa: F401
        except ImportError:
            log.debug("feature_builder not present; artefact may not need it.")

        _model = joblib.load(settings.model_path)

        # Legacy two-file artefacts kept a vectoriser alongside the estimator.
        # A pipeline holds its own, so this is only loaded when it exists and
        # is not empty.
        if (
            settings.vectorizer_path.exists()
            and settings.vectorizer_path.stat().st_size > 0
        ):
            _vectorizer = joblib.load(settings.vectorizer_path)

        _version = getattr(_model, "version_", "trained-0.1")
        log.info(
            "Loaded classifier %s (%s)",
            _version,
            "pipeline" if _vectorizer is None else "estimator + vectoriser",
        )
    except Exception:
        log.exception("Failed to load model artefacts. Falling back to stub.")
        _model = None
        _vectorizer = None


# --------------------------------------------------------------------------
# Stub
# --------------------------------------------------------------------------

# Keyword weights used only when no trained model is present. These exist so
# the pipeline returns a plausible, varying probability during development.
# They are NOT a fallback fraud detector and must never ship as one.
_STUB_SIGNALS: list[tuple[str, float]] = [
    (r"registration fee|processing fee|application fee|placement fee", 0.30),
    (r"visa fee|medical fee|training fee|agency fee", 0.30),
    (r"\bm-?pesa\b|send money|pay before|deposit", 0.25),
    (r"urgent|immediately|limited slots|apply now|hurry", 0.10),
    (r"no interview|no experience needed|no cv required", 0.15),
    (r"earn (very )?high|unlimited income|guaranteed income", 0.20),
    (r"work from home.*earn|quick money|easy money", 0.15),
    (r"passport.*(hold|retain|surrender)", 0.25),
    (r"contract.*on arrival|sign.*after arrival", 0.20),
    (r"@(gmail|yahoo|hotmail|outlook)\.com", 0.10),
]


def _stub_probability(text: str) -> float:
    """Crude keyword score in the range 0.05 to 0.95."""
    if not text.strip():
        return 0.5

    lowered = text.lower()
    score = 0.05
    for pattern, weight in _STUB_SIGNALS:
        if re.search(pattern, lowered):
            score += weight

    # Very short postings are mildly suspicious; genuine ads tend to be long.
    if len(lowered) < 200:
        score += 0.10

    return round(min(score, 0.95), 4)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def predict(text: str) -> ModelResult:
    """Return the probability that this posting is fraudulent."""
    _load()

    if _model is None:
        return ModelResult(
            probability=_stub_probability(text),
            model_version=_version,
            is_stub=True,
        )

    # A pipeline takes raw text. A legacy estimator needs the vectoriser
    # applied first.
    features = [text] if _vectorizer is None else _vectorizer.transform([text])
    probability = float(_model.predict_proba(features)[0][1])

    return ModelResult(
        probability=round(probability, 4),
        model_version=_version,
        is_stub=False,
    )


def is_stub() -> bool:
    """True when running without trained artefacts. Surfaced on /health."""
    _load()
    return _model is None
