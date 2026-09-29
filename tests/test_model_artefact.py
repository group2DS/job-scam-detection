"""Guards on the trained model artefact and the feature builder.

`src/models/classifier.py` catches any load failure and falls back to a
keyword stub, logging the error but continuing to serve. That is the right
behaviour for availability, but it means a corrupt, missing or incompatible
artefact degrades the product silently. Nothing in the UI distinguishes a
real prediction from a stub one.

These tests make that failure loud. They are the check that catches a
pipeline exported with a notebook-local `__main__.TextFeatureBuilder`, which
is the specific regression commit 2c2081a fixed.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.base import clone
from sklearn.exceptions import NotFittedError
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.core.config import get_settings
from src.models import classifier
from src.models.feature_builder import TextFeatureBuilder

SCAM_TEXT = (
    "URGENT hiring! Pay a refundable registration fee of KSh 2000 via M-PESA "
    "to secure your slot. No interview required. Send your passport today."
)

LEGITIMATE_TEXT = (
    "Software Engineer, Safaricom PLC, Nairobi. Requirements: BSc in Computer "
    "Science or related field, three years of experience with distributed "
    "systems, strong Python and SQL. Apply through the careers portal."
)


# ---------------------------------------------------------------------------
# The deployed artefact
# ---------------------------------------------------------------------------


def test_model_artefact_exists():
    settings = get_settings()
    assert settings.model_path.exists(), (
        f"No model artefact at {settings.model_path}. The API will serve stub "
        "predictions. Run the export cell in the modelling notebook."
    )
    assert settings.model_path.stat().st_size > 0, "Model artefact is empty."


def test_api_is_not_serving_stub_predictions():
    """The load path must succeed, not fall back.

    This is the test that fails when a pipeline is exported with a
    notebook-local transformer class, when scikit-learn versions are
    incompatible, or when the artefact is truncated.
    """
    classifier._loaded = False  # force a fresh load attempt
    assert classifier.is_stub() is False, (
        "The classifier fell back to the keyword stub. Check the API logs for "
        "'Failed to load model artefacts'. Common causes: the exported "
        "pipeline references __main__.TextFeatureBuilder instead of "
        "src.models.feature_builder, or the artefact was written by an "
        "incompatible scikit-learn version."
    )


def test_model_separates_an_obvious_scam_from_an_obvious_legitimate_posting():
    """A weak but non-negotiable sanity floor on model quality.

    Not a performance metric. It only asserts that the deployed model has not
    been replaced by something inverted, constant or broken.
    """
    scam = classifier.predict(SCAM_TEXT)
    legit = classifier.predict(LEGITIMATE_TEXT)

    assert scam.is_stub is False and legit.is_stub is False
    assert scam.probability > legit.probability, (
        f"Model scored the scam posting at {scam.probability} and the "
        f"legitimate posting at {legit.probability}. The model may be "
        "inverted or was trained on mislabelled data."
    )
    assert 0.0 <= scam.probability <= 1.0
    assert 0.0 <= legit.probability <= 1.0


def test_model_version_is_stamped():
    """`version_` is surfaced on /health and is how a deployed model is traced
    back to the training run that produced it."""
    result = classifier.predict(LEGITIMATE_TEXT)
    assert result.model_version, "Model version string is empty."
    assert result.model_version != "stub-0.1"
    assert result.model_version != "trained-0.1", (
        "Model exported without a version_ attribute, so it falls back to the "
        "generic default and cannot be traced to a training run."
    )


def test_pipeline_shape_matches_the_serving_contract():
    """classifier.predict passes a list of raw strings straight to the
    pipeline. A pipeline expecting a pre-vectorised matrix would break."""
    import joblib

    model = joblib.load(get_settings().model_path)
    assert isinstance(model, Pipeline)
    proba = model.predict_proba([SCAM_TEXT])
    assert proba.shape == (1, 2)


# ---------------------------------------------------------------------------
# TextFeatureBuilder
# ---------------------------------------------------------------------------


@pytest.fixture
def texts():
    return [SCAM_TEXT, LEGITIMATE_TEXT, "", "Short ad.", "APPLY NOW!!! WhatsApp +254712345678"]


def test_feature_builder_fits_and_transforms(texts):
    fb = TextFeatureBuilder(max_features=100, min_df=1).fit(texts)
    out = fb.transform(texts)
    assert out.shape[0] == len(texts)
    assert out.shape[1] == fb.n_text_features_ + fb.n_numeric_features_


def test_feature_builder_survives_clone(texts):
    """The regression this revision exists to prevent.

    Before the change, `fit` was a no-op and the notebook transplanted an
    already-fitted vectoriser onto the instance. clone() copies constructor
    parameters only, so every cloned transformer lost `tfidf_`, which broke
    cross_val_score, GridSearchCV and CalibratedClassifierCV.
    """
    fitted = TextFeatureBuilder(max_features=100, min_df=1).fit(texts)
    fresh = clone(fitted)

    with pytest.raises(NotFittedError):
        fresh.transform(texts)

    fresh.fit(texts)
    assert fresh.transform(texts).shape == fitted.transform(texts).shape


def test_feature_builder_works_inside_cross_validation(texts):
    """End-to-end proof that the cloning path is usable, which is what the
    whole modelling section depends on."""
    from sklearn.model_selection import cross_val_score

    X = texts * 4
    y = np.array([1, 0, 0, 0, 1] * 4)

    pipe = Pipeline([
        ("features", TextFeatureBuilder(max_features=50, min_df=1)),
        ("classifier", LogisticRegression(max_iter=1000, random_state=42)),
    ])

    scores = cross_val_score(pipe, X, y, cv=3, scoring="accuracy")
    assert len(scores) == 3
    assert np.all(np.isfinite(scores))


def test_feature_builder_params_are_tunable():
    """Parameters must be reachable through the pipeline for GridSearchCV."""
    pipe = Pipeline([
        ("features", TextFeatureBuilder()),
        ("classifier", LogisticRegression()),
    ])
    assert "features__max_features" in pipe.get_params()
    pipe.set_params(features__max_features=123)
    assert pipe.named_steps["features"].max_features == 123


def test_feature_builder_raises_before_fit(texts):
    with pytest.raises(NotFittedError):
        TextFeatureBuilder().transform(texts)


def test_feature_builder_handles_empty_and_missing_text():
    """Real submissions include empty strings and None from failed extraction."""
    fb = TextFeatureBuilder(max_features=50, min_df=1).fit(["some text here", "more text"])
    out = fb.transform(["", None, "text"])
    assert out.shape[0] == 3
    assert np.all(np.isfinite(out.toarray()))


def test_numeric_features_are_computed_correctly():
    fb = TextFeatureBuilder()
    frame = fb._numeric_features([
        "Visit http://scam.example and email me at a@b.com or call +254712345678 NOW URGENT"
    ])
    row = frame.iloc[0]
    assert row["urls_per_100w"] > 0
    assert row["emails_per_100w"] > 0
    assert row["phones_per_100w"] > 0
    assert row["uppercase_ratio"] > 0      # NOW, URGENT
    assert row["digit_ratio"] > 0
    assert row["mean_word_length"] > 0


def test_feature_names_are_recoverable(texts):
    """Coefficient interpretation and the explainability layer both need
    features to map back to readable terms."""
    fb = TextFeatureBuilder(max_features=50, min_df=1).fit(texts)
    names = fb.get_feature_names_out()
    assert len(names) == fb.n_text_features_ + fb.n_numeric_features_
    assert list(names[-6:]) == fb.NUMERIC_COLUMNS

def test_thresholds_match_the_modelling_recommendation():
    """Part 26.3 selected these from a cost-weighted sweep on validation data.
    Changing them without re-running that analysis silently changes what the
    system tells job seekers."""
    s = get_settings()
    assert s.suspicious_threshold == 0.25
    assert s.high_risk_threshold == 0.70