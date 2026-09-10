# Model Export Contract

This contract should be agreed before modelling starts. It allows the API and
the modelling notebook to be developed in parallel and integrated with a
single change.

---

## The contract

The model exposes exactly one capability:

```
text (str)  ->  probability of fraud (float, 0.0 to 1.0)
```

That is the whole interface. The model does not receive registry data, does
not know what a blacklist is, and does not assign a risk tier. Those belong
to the verification and decision stages.

## What to export

Two files, saved with `joblib`, committed to `artifacts/`:

```
artifacts/model.pkl        the fitted estimator
artifacts/vectorizer.pkl   the fitted TF-IDF vectoriser
```

```python
import joblib

joblib.dump(model, "artifacts/model.pkl")
joblib.dump(vectorizer, "artifacts/vectorizer.pkl")
```

The API loads them at startup. If they are absent it runs a keyword stub, so
frontend work is never blocked on modelling.

## Requirements the API depends on

**`predict_proba` must exist**, returning `[[p_legitimate, p_fraud]]`. Use an
estimator that supports it. If you use an SVM, wrap it in
`CalibratedClassifierCV`.

**Class 1 must be fraud.** The API reads `predict_proba(X)[0][1]`.

**The vectoriser must be fitted on the same text construction the API sends.**
The API concatenates title and description with a single space:

```python
text = f"{title} {description}".strip()
```

<mark>If you trainining is on something different, say title + description + requirements,
tell me and I will change `Posting.model_text()` to match. A mismatch here is
silent and will quietly degrade every prediction. </mark>

**Probabilities must be calibrated**, because the decision thresholds are
absolute values (0.35 and 0.70), not percentiles. Check with a reliability
curve. If the model is badly calibrated, wrap it:

```python
from sklearn.calibration import CalibratedClassifierCV
calibrated = CalibratedClassifierCV(base_model, method="sigmoid", cv=5)
```

## Fields that must never enter the model

These leak the target or belong to a later pipeline stage:

```
is_fraud            the target
red_flags           generated from the target
registry_match_status   belongs to verification
blacklist result        belongs to verification
has_company_logo    EMSCAD metadata, F1 0.258 on its own
has_questions       same
telecommuting       same
```

The last three matter more than they look. In the source dataset, 67% of
fraudulent ads lack a company logo against 18% of legitimate ones. Including
that flag means the model does tabular classification on three binary
columns rather than reading the posting, and it will not generalise to a
pasted job description where no such metadata exists.

## Data to train on

Use `data/processed/01_trainable_real.csv`. Real labelled rows only, 4.3%
fraud, which matches the real base rate.

Do not train on the synthetic rows. A model trained on them scores a perfect
1.000 ROC-AUC on synthetic holdout and catches 33% of real fraud at 9%
precision. `02_synthetic_scenarios.csv` is a test fixture, not training data.

## Splitting

Split on the `fingerprint` column, not the row index, so near duplicate
postings cannot appear in both train and test. Stratify on the label.

```python
from sklearn.model_selection import train_test_split

train, test = train_test_split(
    df, test_size=0.2, stratify=df.is_fraud, random_state=42
)
```

## Imbalance

Start with `class_weight="balanced"`. Reach for SMOTE only if that is
insufficient, and only fit it inside the training fold.

Do not rebalance the dataset to 50/50. The thresholds the whole UI depends on
assume calibrated probabilities against a realistic base rate. Rebalancing
breaks them and the three tier output stops meaning anything.

## Metrics to report

Accuracy is meaningless here. Always predicting "legitimate" scores 95.7%
accuracy and 0.000 F1 on the class that matters.

Report instead:

- Recall on the fraud class, the headline number
- Precision on the fraud class
- F1 on the fraud class
- PR-AUC, more informative than ROC-AUC under imbalance
- Confusion matrix, with false negatives called out explicitly

An honest baseline on real data is around **0.65 F1 and 0.96 ROC-AUC**. If a
run reports 0.99, something has leaked. Check it before reporting it.

## Version stamping

Helps trace which model produced which case decision:

```python
model.version_ = "logreg-tfidf-v1"
```

The API reads this and stores it on every referred case.

## Integration test

Once exported, this should run clean:

```python
import joblib

model = joblib.load("artifacts/model.pkl")
vectorizer = joblib.load("artifacts/vectorizer.pkl")

text = "Urgent hiring. Pay a registration fee of KES 5000 via Mpesa."
print(model.predict_proba(vectorizer.transform([text]))[0][1])
```

If that prints a float between 0 and 1, integration is a drop in.
