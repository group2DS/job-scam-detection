"""
Hybrid feature construction for the fraud classifier.

This module exists so the fitted pipeline can be unpickled outside the
notebook that trained it. joblib stores a reference to a class by import path
rather than storing the class body, so a transformer defined in a notebook
cell resolves to `__main__.TextFeatureBuilder` and fails to load anywhere
else. Keeping it here means the API, the tests and the notebook all resolve
the same class.

Author: Cleopas Karanja. Moved from the training notebook unchanged.

Revised 2026-09-28: `fit` now fits the vectoriser and scaler rather than
relying on the training notebook transplanting already-fitted objects onto
the instance. The previous arrangement reproduced the training run exactly,
but it meant `sklearn.base.clone` returned a transformer with no `tfidf_` or
`scaler_`, because clone copies constructor parameters and nothing else.
Every sklearn utility that clones, which includes cross_val_score,
GridSearchCV, cross_val_predict and CalibratedClassifierCV, was therefore
unusable. The feature set and the exclusion of missing-field indicators are
unchanged.

Pipelines pickled before this revision still load, since the class lives at
the same import path and `transform` still reads `tfidf_` and `scaler_`.
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
    needs a string. Length, word count, uppercase ratio, and URL, email and
    phone counts all derive from text already. No missing-field indicators are
    used, since those encode how a posting was submitted rather than whether
    it is fraudulent, and do not generalise across ingestion channels: a
    pasted WhatsApp listing is missing a company name whether or not it is a
    scam, where a scraped web page usually is not.

    Parameters
    ----------
    max_features, ngram_range, min_df, sublinear_tf
        Passed to the internal TfidfVectorizer. Exposed as constructor
        parameters so they can be tuned through a pipeline, for example
        `features__max_features` in a GridSearchCV parameter grid.
    scale_numeric
        Whether to standardise the six numeric features. Tree-based models do
        not need it; linear models do.
    """

    NUMERIC_COLUMNS = [
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
    ) -> None:
        # Assigned unmodified, as sklearn's get_params/clone contract requires.
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.min_df = min_df
        self.sublinear_tf = sublinear_tf
        self.scale_numeric = scale_numeric

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

    def _numeric_features(self, texts) -> pd.DataFrame:
        s = self._as_series(texts)
        out = pd.DataFrame(index=s.index)
        out["text_length"] = s.str.len()
        out["word_count"] = s.str.split().str.len()
        out["url_count"] = s.str.count(r"http|www\.")
        out["email_count"] = s.str.count(r"\b[\w.-]+@[\w.-]+\.\w+\b")
        out["phone_count"] = s.str.count(r"\+?\d[\d\s().-]{7,}\d")
        out["uppercase_count"] = s.str.count(r"\b[A-Z]{3,}\b")
        # word_count is NaN for an empty string, where 0 is the correct value.
        return out[self.NUMERIC_COLUMNS].fillna(0).astype(float)

    # -- sklearn API -------------------------------------------------------

    def fit(self, X, y=None):
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
