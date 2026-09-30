"""Guards that predictions respond to evidence rather than to posting length.

History, because the first version of this module asserted something false.

The deployed model at logreg-hybrid-v4-20260928 scored an identical legitimate
Safaricom accountant advert at 0.575 when truncated to 28 characters and 0.196
at 462, which looked like a length artefact. `text_length` carried the largest
negative coefficient of any numeric feature (-0.2298), and the EDA had already
flagged that EMSCAD legitimate postings average 631 characters against 283 for
fraudulent ones.

Replacing the raw counts with length-invariant densities did not fix it. Nor
did removing the numeric features entirely, nor disabling sublinear TF-IDF
scaling: every variant showed a spread of 0.46 to 0.53. Probing further showed
why. The scores did not decline smoothly with length, they stepped down
between 78 and 139 characters, which is exactly where the prefix first
contained "CPA(K) certification, a bachelor's degree in accounting or
finance". The original test varied *evidence* and attributed the result to
*length*.

The decisive check was padding: repeating a bare title to 456 characters
scored 0.477, against 0.483 for the same content at 37 characters. Length has
no effect. The model reads content.

These tests therefore hold length roughly constant and vary the evidence.
The density feature set was kept regardless, because a raw count that scales
with posting length has no fraud interpretation even when it is not the
dominant term.
"""

from __future__ import annotations

import pytest

from src.models import classifier
from src.models.feature_builder import TextFeatureBuilder

# Comparable length, different evidence. Every probe is a short posting of
# the kind a job seeker actually pastes from a message.
BARE = "Accountant at Safaricom PLC, Nairobi."
WITH_QUALIFICATIONS = (
    "Accountant, Safaricom PLC. CPA(K) and a degree in finance required."
)
WITH_BOTH = (
    "Accountant, Safaricom PLC. CPA(K) required. Apply via our careers portal."
)
SHORT_SCAM = "Accountant needed. Pay KSh 2000 registration fee via M-Pesa."


def _p(text: str) -> float:
    return classifier.predict(text).probability


# ---------------------------------------------------------------------------
# Content, not length
# ---------------------------------------------------------------------------


def test_padding_with_repetition_does_not_change_the_verdict():
    """The check that exonerated length.

    Repeating a bare title until the posting is twelve times longer adds no
    evidence, so it must not change the score. A model reading length would
    move; a model reading content does not.
    """
    padded = (BARE + " ") * 12
    bare, long = _p(BARE), _p(padded)
    assert abs(long - bare) < 0.10, (
        f"Bare title scored {bare:.3f} at {len(BARE)} characters and "
        f"{long:.3f} at {len(padded)}. Repetition adds no information, so a "
        "difference here means the model is reading length."
    )


def test_vocabulary_dilution_weakens_the_classifier_but_not_the_system():
    """Documents a known limitation rather than asserting it away.

    Appending novel vocabulary to a posting reduces the weight TF-IDF places
    on every term it already contained, because the vectors are L2-normalised.
    On the holdout this pushed 7 of 114 fraudulent postings below threshold.
    See notebook section 27.5.

    The rule layer is the mitigation: regular expressions match regardless of
    surrounding text, so a fee demand buried in corporate prose still fires
    upfront_fee and mobile_money, and two strong signals force HIGH_RISK
    independent of what the classifier returns.
    """
    from src.core.schemas import Posting, RiskLevel
    from src.decision import layer
    from src.rules import engine
    from src.verification import registry

    padded = SHORT_SCAM + " " + (
        "Our organisation values professionalism, teamwork and integrity in "
        "all that we do. " * 6
    )

    # The classifier alone is expected to weaken. Recorded, not asserted away.
    assert _p(padded) < _p(SHORT_SCAM)

    posting = Posting(raw_text=padded)
    hits = engine.evaluate(posting)
    assert len(hits) >= 2, (
        "The rule layer must still fire on a diluted scam; it is the only "
        "component that is immune to this effect."
    )

    risk, *_ = layer.combine(
        posting,
        classifier.predict(padded),
        hits,
        registry.verify(posting),
        engine.looks_overseas(posting),
    )
    assert risk != RiskLevel.LOWER_RISK, (
        "A diluted M-Pesa fee demand must not be reported as lower risk."
    )


# ---------------------------------------------------------------------------
# Evidence moves the score in the right direction
# ---------------------------------------------------------------------------


def test_qualification_requirements_lower_the_risk_score():
    """Concrete professional requirements are evidence of a real vacancy."""
    bare, qualified = _p(BARE), _p(WITH_QUALIFICATIONS)
    assert qualified < bare, (
        f"Adding CPA(K) and degree requirements moved the score from "
        f"{bare:.3f} to {qualified:.3f}. Concrete qualifications should "
        "reduce assessed risk, not raise it."
    )


def test_a_short_scam_is_still_flagged():
    """Brevity must not protect a posting that contains a fee demand.

    At roughly the same length as the bare legitimate title, an explicit
    M-Pesa registration fee must score materially higher.
    """
    scam, bare = _p(SHORT_SCAM), _p(BARE)
    assert scam > bare + 0.15, (
        f"Short scam scored {scam:.3f} against {bare:.3f} for a bare "
        "legitimate title of similar length."
    )
    assert scam > 0.5, f"An explicit M-Pesa fee demand scored only {scam:.3f}."


def test_ordering_across_the_evidence_gradient():
    """The full ordering, which is the property the system depends on."""
    scores = {
        "scam": _p(SHORT_SCAM),
        "bare": _p(BARE),
        "qualified": _p(WITH_BOTH),
    }
    assert scores["scam"] > scores["bare"] > scores["qualified"], (
        f"Expected scam > bare > qualified, got {scores}."
    )


# ---------------------------------------------------------------------------
# Feature set
# ---------------------------------------------------------------------------


def test_numeric_features_are_length_invariant():
    """Retained on principle. A raw count that grows with posting length has
    no fraud interpretation, even though it was not the dominant term."""
    fb = TextFeatureBuilder()
    frame = fb._numeric_features([BARE, (BARE + " ") * 12])
    for column in frame.columns:
        a, b = frame[column].iloc[0], frame[column].iloc[1]
        if a == 0 and b == 0:
            continue
        assert abs(a - b) / max(abs(a), 1e-9) < 0.5, (
            f"{column} changed from {a:.3f} to {b:.3f} when the same content "
            "was repeated twelve times."
        )


def test_raw_length_features_are_not_in_the_active_set():
    fb = TextFeatureBuilder()
    assert "text_length" not in fb.NUMERIC_COLUMNS
    assert "word_count" not in fb.NUMERIC_COLUMNS


def test_legacy_feature_set_remains_available_for_older_artefacts():
    """__init__ does not run on unpickle, so an artefact exported before the
    Part 27 revision has no `feature_set` attribute and must keep computing
    the features its scaler was fitted on."""
    assert (
        TextFeatureBuilder(feature_set="legacy").NUMERIC_COLUMNS
        == TextFeatureBuilder.LEGACY_COLUMNS
    )
    fb = TextFeatureBuilder()
    del fb.__dict__["feature_set"]
    assert fb.NUMERIC_COLUMNS == TextFeatureBuilder.LEGACY_COLUMNS


@pytest.mark.parametrize("text", ["", None, "a", "   "])
def test_degenerate_input_does_not_raise(text):
    import numpy as np

    frame = TextFeatureBuilder()._numeric_features([text])
    assert np.all(np.isfinite(frame.to_numpy()))
