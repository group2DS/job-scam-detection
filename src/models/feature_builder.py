"""
Hybrid feature construction for the fraud classifier.

This module exists so the fitted pipeline can be unpickled outside the
notebook that trained it. joblib stores a reference to a class by import path
rather than storing the class body, so a transformer defined in a notebook
cell resolves to `__main__.TextFeatureBuilder` and fails to load anywhere
else. Keeping it here means the API, the tests and the notebook all resolve
the same class.

Author: Cleopas Karanja. Moved from the training notebook unchanged.

Revised 2026-09-28 (a): `fit` now fits the vectoriser and scaler rather than
relying on the training notebook transplanting already-fitted objects onto
the instance. The previous arrangement reproduced the training run exactly,
but it meant `sklearn.base.clone` returned a transformer with no `tfidf_` or
`scaler_`, so every sklearn utility that clones was unusable.

Revised 2026-09-28 (b): the numeric features are now length-invariant.

    The previous feature set used raw `text_length` and `word_count`, which
    made the prediction depend on how much text a person happened to paste.
    Measured on the deployed model, an identical legitimate Safaricom
    accountant advert scored 0.575 at 28 characters and 0.196 at 462, purely
    as a function of length. `text_length` carried the largest negative
    coefficient of any numeric feature (-0.2298), and the six numeric
    features averaged 1.7 times the absolute coefficient of the 260,884 text
    features.

    The cause is corpus construction rather than fraud: EMSCAD legitimate
    postings average 631 characters against 283 for fraudulent ones, which
    the EDA identified in section 20.12 as a source proxy. Raw counts of
    URLs, emails and phone numbers carry the same confound, since a longer
    advert contains more of everything.

    The signals themselves are real, so they are retained as densities per
    100 words rather than dropped. This is the same reasoning the original
    docstring applied to missing-field indicators: a feature that encodes how
    a posting was submitted rather than whether it is fraudulent does not
    generalise across ingestion channels, and this system's primary channel
    is a job seeker pasting a few lines from WhatsApp.

Pipelines pickled before either revision still load. `feature_set` defaults
to "legacy" when absent from the unpickled instance, so an older artefact
continues to compute the features it was fitted with.
"""

from __future__ import annotations

import pandas as pd
from scipy.sparse import csr_matrix, hstack
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.exceptions import NotFittedError
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler


class TextFeatureBuilder(BaseEstimator, TransformerMixin):
    """Builds the hybrid TF-IDF and structured feature matrix from raw text
    alone, with no parsed posting fields required.

    Deliberately decoupled from any API schema (Posting or otherwise): it only
    needs a string. Contact-detail density and shouting ratio all derive from
    text already. No missing-field indicators are used, since those encode how
    a posting was submitted rather than whether it is fraudulent, and do not
    generalise across ingestion channels: a pasted WhatsApp listing is missing
    a company name whether or not it is a scam, where a scraped web page
    usually is not.

    Parameters
    ----------
    max_features, ngram_range, min_df, sublinear_tf
        Passed to the internal TfidfVectorizer. Exposed as constructor
        parameters so they can be tuned through a pipeline, for example
        `features__max_features` in a GridSearchCV parameter grid.
    scale_numeric
        Whether to standardise the numeric features. Tree-based models do not
        need it; linear models do.
    feature_set
        "density" (default) uses length-invariant rates. "legacy" reproduces
        the original raw-count features and exists so that artefacts exported
        before 2026-09-28 continue to load and score identically.
    """

    # Length-invariant. Counts are expressed per 100 words so that the same
    # posting scores the same whether pasted in full or in part.
    DENSITY_COLUMNS = [
        "urls_per_100w",
        "emails_per_100w",
        "phones_per_100w",
        "uppercase_ratio",
        "digit_ratio",
        "mean_word_length",
    ]

    # The original feature set. Retained for backwards compatibility only.
    LEGACY_COLUMNS = [
        "text_length",
        "word_count",
        "url_count",
        "email_count",
        "phone_count",
        "uppercase_count",
    ]

    def __init__(
        self,
        max_features: int | None = 50_000,
        ngram_range: tuple[int, int] = (1, 2),
        min_df: int = 2,
        sublinear_tf: bool = True,
        scale_numeric: bool = True,
        feature_set: str = "density",
    ) -> None:
        # Assigned unmodified, as sklearn's get_params/clone contract requires.
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.min_df = min_df
        self.sublinear_tf = sublinear_tf
        self.scale_numeric = scale_numeric
        self.feature_set = feature_set

    # -- feature-set selection --------------------------------------------

    @property
    def _active_feature_set(self) -> str:
        """Artefacts pickled before this revision have no `feature_set`
        attribute, because __init__ does not run on unpickle. Those were
        fitted on the raw-count features, so they must keep using them."""
        return getattr(self, "feature_set", "legacy")

    @property
    def NUMERIC_COLUMNS(self) -> list[str]:
        """The active numeric columns. Kept as a property under the original
        name so existing callers, tests and notebook cells are unaffected."""
        return (
            self.LEGACY_COLUMNS
            if self._active_feature_set == "legacy"
            else self.DENSITY_COLUMNS
        )

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _as_series(X) -> pd.Series:
        """Accept a list, ndarray, Series or single-column frame of text.

        The index is reset so the numeric frame built from it always aligns,
        including when a caller passes a slice of a larger frame.
        """
        if isinstance(X, pd.DataFrame):
            if X.shape[1] != 1:
                raise ValueError(
                    "TextFeatureBuilder expects raw text, but received a "
                    f"DataFrame with {X.shape[1]} columns. Pass a single text "
                    "column or a list of strings."
                )
            X = X.iloc[:, 0]
        return pd.Series(X, dtype="object").reset_index(drop=True).fillna("")

    def _legacy_features(self, s: pd.Series) -> pd.DataFrame:
        out = pd.DataFrame(index=s.index)
        out["text_length"] = s.str.len()
        out["word_count"] = s.str.split().str.len()
        out["url_count"] = s.str.count(r"http|www\.")
        out["email_count"] = s.str.count(r"\b[\w.-]+@[\w.-]+\.\w+\b")
        out["phone_count"] = s.str.count(r"\+?\d[\d\s().-]{7,}\d")
        out["uppercase_count"] = s.str.count(r"\b[A-Z]{3,}\b")
        return out

    def _density_features(self, s: pd.Series) -> pd.DataFrame:
        """Rates rather than counts, so nothing scales with posting length.

        Every column is bounded or normalised by word count, so truncating a
        posting leaves the values broadly unchanged. `text_length` and
        `word_count` are deliberately absent: both proved to encode corpus
        provenance rather than fraud.
        """
        words = s.str.split().str.len().fillna(0)
        chars = s.str.len().clip(lower=1)
        # Guarded so an empty or single-word posting cannot divide by zero.
        per_100 = 100.0 / words.clip(lower=1)

        out = pd.DataFrame(index=s.index)
        out["urls_per_100w"] = s.str.count(r"http|www\.") * per_100
        out["emails_per_100w"] = s.str.count(r"\b[\w.-]+@[\w.-]+\.\w+\b") * per_100
        out["phones_per_100w"] = s.str.count(r"\+?\d[\d\s().-]{7,}\d") * per_100
        # Shouting, as a share of words rather than a raw tally.
        out["uppercase_ratio"] = s.str.count(r"\b[A-Z]{3,}\b") * per_100 / 100.0
        # Fee amounts, phone numbers and "KSh 2000" push this up.
        out["digit_ratio"] = s.str.count(r"\d") / chars
        # Separates terse informal wording from formal advert prose.
        out["mean_word_length"] = (chars - words.clip(lower=0)) / words.clip(lower=1)
        return out

    def _numeric_features(self, texts) -> pd.DataFrame:
        s = self._as_series(texts)
        columns = self.NUMERIC_COLUMNS
        out = (
            self._legacy_features(s)
            if self._active_feature_set == "legacy"
            else self._density_features(s)
        )
        # word_count is NaN for an empty string, where 0 is the correct value.
        return out[columns].fillna(0).replace([float("inf"), float("-inf")], 0).astype(float)

    # -- sklearn API -------------------------------------------------------

    def fit(self, X, y=None):
        if self._active_feature_set not in {"density", "legacy"}:
            raise ValueError(
                f"feature_set must be 'density' or 'legacy', "
                f"got {self.feature_set!r}"
            )

        texts = self._as_series(X)

        self.tfidf_ = TfidfVectorizer(
            max_features=self.max_features,
            ngram_range=self.ngram_range,
            min_df=self.min_df,
            sublinear_tf=self.sublinear_tf,
        ).fit(texts)

        numeric = self._numeric_features(texts)
        self.scaler_ = (
            StandardScaler().fit(numeric) if self.scale_numeric else None
        )

        self.n_features_in_ = 1
        self.n_text_features_ = len(self.tfidf_.vocabulary_)
        self.n_numeric_features_ = len(self.NUMERIC_COLUMNS)
        return self

    def transform(self, X):
        if not hasattr(self, "tfidf_"):
            raise NotFittedError(
                "TextFeatureBuilder has not been fitted. Call fit before "
                "transform, or load a pipeline that was fitted and exported "
                "by the training notebook."
            )

        texts = self._as_series(X)
        text_features = self.tfidf_.transform(texts)

        numeric = self._numeric_features(texts)
        # `scaler_` may be absent on a pipeline pickled before this revision.
        scaler = getattr(self, "scaler_", None)
        numeric_features = (
            scaler.transform(numeric) if scaler is not None else numeric.to_numpy()
        )

        return hstack([text_features, csr_matrix(numeric_features)]).tocsr()

    def get_feature_names_out(self, input_features=None):
        """Needed to read model coefficients back as human-readable terms.

        The explainability layer and the EDA follow-up both depend on being
        able to name the features a linear model weighted most heavily.
        """
        if not hasattr(self, "tfidf_"):
            raise NotFittedError("TextFeatureBuilder has not been fitted.")
        import numpy as np

        return np.concatenate(
            [
                self.tfidf_.get_feature_names_out(),
                np.asarray(self.NUMERIC_COLUMNS, dtype=object),
            ]
        )

    def __sklearn_tags__(self):
        tags = super().__sklearn_tags__()
        tags.input_tags.string = True
        tags.input_tags.two_d_array = False
        return tags
