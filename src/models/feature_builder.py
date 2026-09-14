"""
Hybrid feature construction for the fraud classifier.

This module exists so the fitted pipeline can be unpickled outside the
notebook that trained it. joblib stores a reference to a class by import path
rather than storing the class body, so a transformer defined in a notebook
cell resolves to `__main__.TextFeatureBuilder` and fails to load anywhere
else. Keeping it here means the API, the tests and the notebook all resolve
the same class.

Author: Cleopas Karanja. Moved from the training notebook unchanged.
"""

from __future__ import annotations

import pandas as pd
from scipy.sparse import hstack
from sklearn.base import BaseEstimator, TransformerMixin


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
    """

    NUMERIC_COLUMNS = [
        "text_length",
        "word_count",
        "url_count",
        "email_count",
        "phone_count",
        "uppercase_count",
    ]

    def _numeric_features(self, texts) -> pd.DataFrame:
        s = pd.Series(texts, dtype="object").fillna("")
        out = pd.DataFrame(index=s.index)
        out["text_length"] = s.str.len()
        out["word_count"] = s.str.split().str.len()
        out["url_count"] = s.str.count(r"http|www\.")
        out["email_count"] = s.str.count(r"\b[\w.-]+@[\w.-]+\.\w+\b")
        out["phone_count"] = s.str.count(r"\+?\d[\d\s().-]{7,}\d")
        out["uppercase_count"] = s.str.count(r"\b[A-Z]{3,}\b")
        return out[self.NUMERIC_COLUMNS]

    def fit(self, X, y=None):
        # Deliberately not fitting a fresh TF-IDF or scaler here. The training
        # notebook transplants the already-fitted tfidf_hybrid and scaler onto
        # this transformer, so the pipeline reproduces the exact numbers from
        # the training run rather than refitting on whatever it is given.
        return self

    def transform(self, X):
        texts = pd.Series(X, dtype="object").fillna("")
        text_features = self.tfidf_.transform(texts)
        numeric_features = self.scaler_.transform(self._numeric_features(texts))
        return hstack([text_features, numeric_features]).tocsr()
