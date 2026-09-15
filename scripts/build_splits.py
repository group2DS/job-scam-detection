"""
Rebuild the three provenance splits from the merged dataset.

Run this once, locally, from the repository root:

    python build_splits.py path/to/final_job_spam_dataset.csv

Produces, in data/processed/:

    01_trainable_real.csv       real labelled rows      -> trains the model
    02_synthetic_scenarios.csv  generated rows          -> test fixtures only
    03_kenyan_unlabelled.csv    real Kenyan postings    -> annotation pool

The splits exist because the three groups have different epistemic status.
Mixing them produced a 0.99 ROC-AUC that collapsed to 0.14 F1 on real fraud.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("data/processed")

COLUMNS = [
    "title", "company", "location", "industry_category", "work_type",
    "salary_range", "experience_level", "min_qualification", "description",
    "requirements", "source_url", "source_platform", "is_fraud", "data_source",
    "label_source", "label_confidence", "is_synthetic", "fingerprint",
]


def normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    lowered = re.sub(r"[^a-z0-9 ]", " ", str(text).lower())
    return re.sub(r"\s+", " ", lowered).strip()


def main(source: str) -> None:
    df = pd.read_csv(source, low_memory=False)
    print(f"loaded {len(df):,} rows from {source}")

    # Fingerprint on normalised text so near duplicates cannot straddle a
    # train/test boundary later. Splitting must be done on this column.
    df["_text"] = (
        df.title.fillna("") + " "
        + df.description.fillna("") + " "
        + df.requirements.fillna("")
    )
    df["fingerprint"] = df._text.map(
        lambda t: hashlib.md5(normalise(t).encode()).hexdigest()
    )

    before = len(df)
    df = df.drop_duplicates(subset="fingerprint", keep="first").copy()
    print(f"deduplicated: {before:,} -> {len(df):,} ({before - len(df):,} removed)")

    # Provenance. An assumed label must never be mistaken for a verified one.
    synthetic = df.data_source == "synthetic_40k"
    df["label_source"] = np.where(
        synthetic, "synthetic_generation",
        np.where(df.is_fraud.notna(), "original_dataset", "unlabelled"),
    )
    df["label_confidence"] = np.where(
        synthetic, "low", np.where(df.is_fraud.notna(), "high", "none")
    )
    df["is_synthetic"] = synthetic.astype(int)

    real = df[(~synthetic) & (df.is_fraud.notna())]
    generated = df[synthetic]
    kenyan = df[(~synthetic) & (df.is_fraud.isna())]

    OUT.mkdir(parents=True, exist_ok=True)
    real[COLUMNS].to_csv(OUT / "01_trainable_real.csv", index=False)
    generated[COLUMNS].to_csv(OUT / "02_synthetic_scenarios.csv", index=False)
    kenyan[COLUMNS].to_csv(OUT / "03_kenyan_unlabelled.csv", index=False)

    fraud = int(real.is_fraud.sum())
    print()
    print(f"01_trainable_real.csv       {len(real):>7,}  "
          f"fraud {fraud:,} ({real.is_fraud.mean() * 100:.1f}%)")
    print(f"02_synthetic_scenarios.csv  {len(generated):>7,}  test fixtures only")
    print(f"03_kenyan_unlabelled.csv    {len(kenyan):>7,}  no labels")
    print()
    print("Kenyan platforms:")
    for platform, count in kenyan.source_platform.value_counts().items():
        print(f"  {platform:<28} {count:>6,}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python build_splits.py <merged_dataset.csv>")
    main(sys.argv[1])
