#!/usr/bin/env python
"""Append Part 27 (length-invariant retrain) and patch the Part 22 guard.

Usage:
    python build_part27.py notebooks/02_job_scam_detection.ipynb [--dry-run]
"""

import argparse
import json
import shutil

MARKER = "## Part 27: Removing the length artefact"

OLD_GUARD = '''assert TextFeatureBuilder.NUMERIC_COLUMNS == [
    "text_length", "word_count", "url_count",
    "email_count", "phone_count", "uppercase_count",
], "Feature builder numeric columns changed; re-check for missingness indicators."
print("\\nPASS feature builder derives numeric features from text only.")'''

NEW_GUARD = '''# NUMERIC_COLUMNS became an instance property in the Part 27 revision, so that
# artefacts pickled before that change keep computing the features they were
# fitted on. The guard checks the active set rather than a hardcoded list.
_fb_check = TextFeatureBuilder()
assert _fb_check.NUMERIC_COLUMNS == TextFeatureBuilder.DENSITY_COLUMNS, (
    "Feature builder numeric columns changed; re-check for missingness "
    "indicators and for features that scale with posting length."
)
assert "text_length" not in _fb_check.NUMERIC_COLUMNS
assert "word_count" not in _fb_check.NUMERIC_COLUMNS
print("\\nPASS feature builder derives numeric features from text only.")
print("PASS no raw length feature is present (see Part 27).")'''


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
            "source": text.rstrip().splitlines(keepends=True)}


CELLS = []

CELLS.append(md("""\
## Part 27: Removing the length artefact

Part 26 exported `logreg-hybrid-v4-20260928` and closed the modelling work. Probing the deployed model end to end then surfaced a defect that none of the validation or holdout metrics could detect.

The same legitimate Safaricom accountant advert, truncated to different lengths:

| Length | Probability |
| --- | --- |
| 28 characters | 0.575 |
| 78 characters | 0.587 |
| 139 characters | 0.320 |
| 211 characters | 0.270 |
| 462 characters | 0.196 |

**A spread of 0.380 on identical content.** At 78 characters the posting sits in the suspicious tier; at 462 it is below threshold. Padding is just as effective in the other direction: adding neutral corporate boilerplate to an M-Pesa fee scam halved its score, from 0.2235 to 0.1071.

The cause is in the feature set. Reading the coefficients back from the exported model:

| Numeric feature | Coefficient |
| --- | --- |
| `text_length` | **-0.2298** |
| `word_count` | -0.1327 |
| `uppercase_count` | +0.2170 |
| `phone_count` | +0.2011 |
| `email_count` | -0.0832 |
| `url_count` | -0.0510 |

Mean absolute coefficient across the six numeric features is 0.1525, against 0.0894 across all 260,884 text features. Six features carry 1.7 times the average weight of the vocabulary, and the two largest negatives are the two pure length measures.

This is the EDA finding from section 20.12 reaching production. EMSCAD legitimate postings average 631 characters against 283 for fraudulent ones, so within that corpus "long" genuinely predicts "legitimate". It is a property of how the corpus was assembled, not of fraud. The raw counts of URLs, emails and phone numbers carry the same confound, since a longer advert contains more of everything.

**Why the metrics missed it.** Every EMSCAD posting is a full scraped advert, so validation and holdout contain no short postings to reveal the dependence. The deployed system's primary submission channel is a job seeker pasting a few lines from a WhatsApp message. The evaluation data has no examples of the input the product actually receives.

It also contradicts the reasoning already written into `feature_builder.py`, which excluded missing-field indicators because they "encode how a posting was submitted rather than whether it is fraudulent, and do not generalise across ingestion channels". That argument applies unchanged to raw length.
"""))

CELLS.append(md("""\
### 27.1 Length-invariant features

The signals are real; the scaling is the problem. A posting containing three phone numbers in twenty words is different from one containing three in six hundred, and a raw count cannot tell them apart.

| Removed | Replaced by | Reason |
| --- | --- | --- |
| `text_length` | dropped | Pure channel artefact, no fraud interpretation |
| `word_count` | dropped | Same |
| `url_count` | `urls_per_100w` | Density rather than tally |
| `email_count` | `emails_per_100w` | Density rather than tally |
| `phone_count` | `phones_per_100w` | Density rather than tally |
| `uppercase_count` | `uppercase_ratio` | Shouting as a share of words |
| | `digit_ratio` | New: fee amounts and numbers as a share of characters |
| | `mean_word_length` | New: separates terse informal wording from advert prose |

`digit_ratio` and `mean_word_length` replace the two dropped features so the numeric block keeps its width. Both are bounded, both are length-invariant, and unlike the features they replace both have a plausible fraud interpretation: "KSh 2000", till numbers and phone numbers all raise digit density, and scam postings tend toward shorter, plainer words than formal advert prose.

The change is in `src/models/feature_builder.py`. `NUMERIC_COLUMNS` is now a property returning either the new `DENSITY_COLUMNS` or the original `LEGACY_COLUMNS`, selected by a `feature_set` constructor parameter that defaults to `"density"`. An artefact pickled before this revision has no `feature_set` attribute, because `__init__` does not run on unpickle, so the property falls back to `"legacy"` and the older model continues to compute exactly the features it was fitted on.
"""))

CELLS.append(code('''\
# Reload the module so the notebook picks up the revised feature builder
# without a kernel restart.
import importlib

import src.models.feature_builder as fb_module

importlib.reload(fb_module)
from src.models.feature_builder import TextFeatureBuilder  # noqa: E402

print("Active feature set:", TextFeatureBuilder().NUMERIC_COLUMNS)
print("Legacy feature set:", TextFeatureBuilder.LEGACY_COLUMNS)

# The defect, measured on the features alone before any retraining.
prefix_base = (
    "Accountant at Safaricom PLC, Nairobi. We are seeking a qualified "
    "accountant to join our finance team. Requirements: CPA(K) certification, "
    "a bachelor's degree in accounting or finance, and at least three years "
    "of experience in financial reporting and reconciliation. "
    "Responsibilities include preparing monthly management accounts, "
    "supporting the annual audit, and maintaining the fixed asset register."
)
prefixes = [" ".join(prefix_base.split()[:n]) for n in [4, 8, 12, 20, 32, 48, 60]]

print("\\nLegacy features across prefixes of one posting:")
print(TextFeatureBuilder(feature_set="legacy")
      ._numeric_features(prefixes).round(2).to_string(index=False))

print("\\nDensity features across the same prefixes:")
print(TextFeatureBuilder(feature_set="density")
      ._numeric_features(prefixes).round(3).to_string(index=False))'''))

CELLS.append(md("""\
### 27.2 Retrain and compare

The comparison holds everything constant except the feature set: same training rows, same `C=10.0`, same uncapped vocabulary, same grouped splits from Part 22.

Two questions. Does the length dependence actually go away, and what does removing it cost on the EMSCAD metrics? Some loss is expected and acceptable, because `text_length` was genuinely predictive **within this corpus**. The point is that it predicts provenance rather than fraud, so paying for its removal buys correctness on the traffic the system serves.
"""))

CELLS.append(code('''\
def fit_variant(feature_set):
    return Pipeline([
        ("features", TextFeatureBuilder(
            max_features=None, ngram_range=(1, 2), min_df=2,
            feature_set=feature_set,
        )),
        ("classifier", LogisticRegression(
            C=10.0, class_weight="balanced", max_iter=2000,
            solver="liblinear", random_state=MODEL_SEED,
        )),
    ]).fit(X_train, y_train)


variants = {"legacy (raw counts)": fit_variant("legacy"),
            "density (length-invariant)": fit_variant("density")}

rows = []
for name, model in variants.items():
    proba = model.predict_proba(X_val)[:, 1]
    rows.append({
        "feature set": name,
        "pr_auc": average_precision_score(y_val, proba),
        "roc_auc": roc_auc_score(y_val, proba),
        "brier": brier_score_loss(y_val, proba),
    })

comparison = pd.DataFrame(rows).set_index("feature set").round(4)
print("Validation performance, identical apart from the feature set:\\n")
print(comparison.to_string())
print(f"\\nCost of removing the length features: "
      f"{comparison.loc['density (length-invariant)', 'pr_auc'] - comparison.loc['legacy (raw counts)', 'pr_auc']:+.4f} PR-AUC")'''))

CELLS.append(code('''\
# Does the length dependence actually go away?
print("Probability across prefixes of the same legitimate posting:\\n")
spread_rows = []
for name, model in variants.items():
    scores = model.predict_proba(prefixes)[:, 1]
    spread_rows.append({
        "feature set": name,
        **{f"{len(p)}ch": round(s, 3) for p, s in zip(prefixes, scores)},
        "spread": round(scores.max() - scores.min(), 3),
    })
print(pd.DataFrame(spread_rows).to_string(index=False))

# And in the other direction: can a scam be hidden by padding?
scam = ("Urgent hiring. Pay a refundable registration fee of KSh 2000 via "
        "M-Pesa to secure your slot.")
padded = scam + " " + ("Our organisation values professionalism, teamwork and "
                       "integrity in all that we do. " * 6)

print("\\nScam posting, before and after padding with neutral boilerplate:\\n")
for name, model in variants.items():
    bare = model.predict_proba([scam])[0][1]
    pad = model.predict_proba([padded])[0][1]
    print(f"  {name:28} {bare:.3f} -> {pad:.3f}  ({pad - bare:+.3f})")'''))

CELLS.append(code('''\
# What the new numeric features are actually worth to the model.
density_model = variants["density (length-invariant)"]
names = density_model.named_steps["features"].get_feature_names_out()
coefs = density_model.named_steps["classifier"].coef_[0]
n_numeric = density_model.named_steps["features"].n_numeric_features_

print("Numeric feature coefficients (density set):")
for name, coef in zip(names[-n_numeric:], coefs[-n_numeric:]):
    print(f"  {name:20} {coef:+.4f}")

print(f"\\nMean |coef| text features:    {np.abs(coefs[:-n_numeric]).mean():.4f}")
print(f"Mean |coef| numeric features: {np.abs(coefs[-n_numeric:]).mean():.4f}")
print(f"Ratio: {np.abs(coefs[-n_numeric:]).mean() / np.abs(coefs[:-n_numeric]).mean():.1f}x")
print("\\nFor comparison, the legacy set had text_length at -0.2298 and a")
print("numeric-to-text ratio of 1.7x.")'''))

CELLS.append(md("""\
### 27.3 Holdout re-evaluation

The holdout was opened once in Part 26. Using it again is a deliberate and declared choice rather than an oversight.

The alternative is worse. Shipping a model with a known defect because the clean evaluation has been spent would be optimising for the appearance of methodological purity over the correctness of the deployed system. What matters is that the second use is declared, that the feature change was motivated by a defect found outside the holdout, and that no hyperparameter was selected using it.

**Both configurations are reported side by side**, so the comparison stands on its own regardless of how much weight the second holdout number carries.
"""))

CELLS.append(code('''\
X_final = pd.concat([real_train["model_text"], real_val["model_text"]])
y_final = pd.concat([real_train["target"], real_val["target"]])

final_density = Pipeline([
    ("features", TextFeatureBuilder(max_features=None, ngram_range=(1, 2),
                                    min_df=2, feature_set="density")),
    ("classifier", LogisticRegression(C=10.0, class_weight="balanced",
                                      max_iter=2000, solver="liblinear",
                                      random_state=MODEL_SEED)),
]).fit(X_final, y_final)

holdout_density = blended(final_density.predict_proba(X_holdout)[:, 1], X_holdout)

print("Holdout, both configurations:\\n")
print(f"{'':28} {'PR-AUC':>8} {'ROC-AUC':>8} {'Brier':>8}")
print(f"{'v4 legacy (Part 26)':28} {0.8164:8.4f} {0.9730:8.4f} {0.0186:8.4f}")
print(f"{'v5 density (this section)':28} "
      f"{average_precision_score(y_holdout, holdout_density):8.4f} "
      f"{roc_auc_score(y_holdout, holdout_density):8.4f} "
      f"{brier_score_loss(y_holdout, holdout_density):8.4f}")

flagged = holdout_density >= RECOMMENDED_THRESHOLD
tp = int((flagged & (y_holdout == 1)).sum())
fp = int((flagged & (y_holdout == 0)).sum())
fn = int((~flagged & (y_holdout == 1)).sum())
print(f"\\nAt threshold {RECOMMENDED_THRESHOLD}: caught {tp}/{tp + fn}, "
      f"missed {fn}, false alarms {fp}, recall {tp / (tp + fn):.1%}")
print("v4 legacy for comparison: caught 92/114, missed 22, false alarms 55, recall 80.7%")'''))

CELLS.append(code('''\
# Export, replacing the Part 26 artefact.
from datetime import date

final_density.version_ = f"logreg-hybrid-v5-density-{date.today():%Y%m%d}"

model_path = ARTIFACT_DIR / "model.pkl"
joblib.dump(final_density, model_path)
print(f"Exported {model_path} ({model_path.stat().st_size / 1e6:.1f} MB)")
print(f"Version: {final_density.version_}")

builder = final_density.named_steps["features"]
assert type(builder).__module__ == "src.models.feature_builder"
assert "text_length" not in builder.NUMERIC_COLUMNS
print(f"Feature set: {builder.NUMERIC_COLUMNS}")

# Integration test through the application's own loading path.
from src.models import classifier as api_classifier

importlib.reload(api_classifier)
api_classifier._loaded = False
assert api_classifier.is_stub() is False, "API fell back to the stub classifier."

print("\\nEnd-to-end through src.models.classifier:")
scores = [api_classifier.predict(p).probability for p in prefixes]
print(f"  legitimate posting across prefixes: {[round(s, 3) for s in scores]}")
print(f"  spread: {max(scores) - min(scores):.3f}  (was 0.380 under v4)")
for text, label in [(scam, "M-Pesa scam"), (prefix_base, "Safaricom advert")]:
    print(f"  {api_classifier.predict(text).probability:.3f}  {label}")

print("\\nRun `pytest tests/test_length_invariance.py` to confirm outside the notebook.")'''))

CELLS.append(md("""\
### 27.4 Findings

*Complete from the results above.*

Record:

- what removing the length features cost on validation and holdout PR-AUC
- the prefix spread before and after, and whether padding still hides a scam
- the new numeric coefficients, and whether the numeric block still outweighs the vocabulary
- the exported version, and whether `tests/test_length_invariance.py` now passes
- that the holdout was opened a second time, deliberately and declared

The wider point for the report: this defect was visible in the EDA, survived model selection, cross-validation, calibration and a clean holdout evaluation, and was found only by probing the deployed path with input resembling what a real user submits. **Validation metrics measured what the corpus contained, not what the product receives.** Any evaluation drawn from a single corpus carries that risk, and the mitigation is to test the deployed path with realistic input rather than to trust the metric.
"""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("notebook")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.notebook, encoding="utf-8") as fh:
        nb = json.load(fh)
    cells = nb["cells"]

    for cell in cells:
        if MARKER in "".join(cell["source"]):
            raise SystemExit("FAILED: Part 27 already present.")

    # Patch the Part 22 guard, which hardcodes the legacy column list.
    hits = [i for i, c in enumerate(cells)
            if c["cell_type"] == "code" and OLD_GUARD in "".join(c["source"])]
    if len(hits) == 1:
        i = hits[0]
        src = "".join(cells[i]["source"]).replace(OLD_GUARD, NEW_GUARD)
        cells[i]["source"] = src.splitlines(keepends=True)
        cells[i]["outputs"] = []
        cells[i]["execution_count"] = None
        print(f"  - cell {i}: Part 22 guard updated (CODE, re-run this cell)")
    else:
        print(f"  ! Part 22 guard not found ({len(hits)} matches); patch it by hand")

    cells.extend(CELLS)
    print(f"  - appended {len(CELLS)} cells "
          f"({sum(c['cell_type'] == 'code' for c in CELLS)} code, "
          f"{sum(c['cell_type'] == 'markdown' for c in CELLS)} markdown)")

    if args.dry_run:
        print("\nDry run, nothing written.")
        return

    shutil.copy2(args.notebook, args.notebook + ".bak")
    with open(args.notebook, "w", encoding="utf-8") as fh:
        json.dump(nb, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"\nWritten. Backup at {args.notebook}.bak")
    print("\nRe-run the Part 22 guard cell, then run Part 27.")


if __name__ == "__main__":
    main()
