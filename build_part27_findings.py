#!/usr/bin/env python
"""Write Part 27.4 findings.

Usage:
    python build_part27_findings.py notebooks/02_job_scam_detection.ipynb [--dry-run]
"""

import argparse
import json
import shutil

FINDINGS = """\
### 27.4 Findings

**The length artefact was not a length artefact.** The investigation reversed its own conclusion, and the reversal is the useful part.

#### What was measured

The trigger was real: the same legitimate Safaricom accountant advert scored 0.575 truncated to 28 characters and 0.196 at 462, a spread of 0.380, and `text_length` carried the largest negative coefficient of any numeric feature at -0.2298. The EDA had already flagged in section 20.12 that EMSCAD legitimate postings average 631 characters against 283 for fraudulent ones, so a length confound was the obvious explanation.

Replacing the raw counts with length-invariant densities did not fix it. The spread went from 0.380 to 0.452.

| Variant | Validation PR-AUC | Prefix spread |
| --- | --- | --- |
| Legacy raw counts | 0.7987 | 0.458 |
| Density, length-invariant | 0.7906 | 0.500 |
| TF-IDF only, no numeric features | 0.7986 | 0.463 |
| TF-IDF only, `sublinear_tf=False` | 0.7806 | 0.504 |

Removing the numeric block entirely left the effect intact, which exonerated the feature engineering completely.

#### The actual explanation

The scores did not decline smoothly with length. They stepped:

```
 28ch   52ch   78ch  |  139ch  211ch  358ch  400ch
0.579  0.663  0.590  |  0.253  0.211  0.241  0.205
```

Flat, then a step, then flat again. The step falls exactly where the prefix first contains `"Requirements: CPA(K) certification, a bachelor's degree in accounting or finance"`.

The first three prefixes are a job title, a company name and a generic sentence. **None of that is evidence of legitimacy.** The model was not penalising brevity; it was correctly reporting that it had seen no qualifications, no application process and no concrete detail. Those arrive at 139 characters and the score drops accordingly.

The decisive test holds content constant and varies only length:

| Probe | Length | Score |
| --- | --- | --- |
| Bare title and company | 37 ch | 0.483 |
| Same content repeated twelve times | 456 ch | **0.477** |

Padding a posting to twelve times its length changes the score by 0.006. **Length has no effect.**

Varying evidence at constant length produces the movement instead:

| Probe | Length | Score |
| --- | --- | --- |
| Short scam, M-Pesa registration fee | 60 ch | **0.766** |
| Bare title and company | 37 ch | 0.483 |
| Plus application route | 66 ch | 0.551 |
| Plus qualifications and route | 73 ch | 0.402 |
| Plus qualifications, CPA(K) | 67 ch | **0.323** |

Adding professional qualifications lowers the score by 0.16 at essentially identical length, and a 60-character fee demand is flagged at 0.766. The model reads content, and reads it sensibly.

**The original test was wrong.** It varied evidence across its prefixes and attributed the resulting variation to length. A test that asserts a false property is worse than no test, so `tests/test_length_invariance.py` is replaced by `tests/test_evidence_sensitivity.py`, which holds length roughly constant and varies evidence.

#### The density feature set is kept anyway

Two reasons, neither of which is the one the change was made for.

It is marginally better where it counts. On the holdout the density model catches 93 of 114 fraudulent postings against 92, with 54 false alarms against 55: recall 81.6% against 80.7%.

| | Validation PR-AUC | Holdout PR-AUC | Holdout ROC-AUC | Holdout recall |
| --- | --- | --- | --- | --- |
| v4 legacy | 0.7987 | 0.8164 | 0.9730 | 80.7% |
| **v5 density** | 0.7906 | 0.8071 | 0.9685 | **81.6%** |

And it is more defensible on principle. A raw count of characters or words has no fraud interpretation, only a corpus-specific correlation, so it should not be a model input regardless of how much weight it happened to carry. That is the same argument the original `feature_builder.py` docstring made for excluding missing-field indicators, applied consistently.

Exported as **`logreg-hybrid-v5-density-20260928`**.

One caveat to record: the numeric block still carries disproportionate weight, now 2.2 times the mean absolute text coefficient against 1.7 before, with `emails_per_100w` at -0.4168 the largest single coefficient in the model. Six features outweighing 260,884 is worth revisiting, but it is a tuning question rather than a defect.

Gradient boosting re-ran on the density features at PR-AUC 0.6324, against 0.6606 under the legacy set. It remains last in the ladder and is still not carried forward.

#### The product finding that came out of it

A posting with no rule hits scoring around 0.48 is not suspicious in any useful sense. It is **unevaluable**: the system has seen nothing incriminating and nothing reassuring, and reporting that as elevated risk tells a job seeker something the model does not actually know.

Sizing it on the validation set:

| | Count |
| --- | --- |
| Postings scoring 0.25 to 0.70 | 6 (0.3%) |
| Of those, with no rule hit | 5 |
| Actually fraudulent | **0** |
| Actually legitimate | 5 |

Too rare on this corpus to justify a new risk tier. **But the corpus is the wrong place to size it.** Median word count in that band was 152 against 239 overall, and every short hand-written probe above landed squarely inside it. EMSCAD consists of complete scraped adverts; the deployed system receives whatever a job seeker pastes out of a WhatsApp message. The band is nearly empty here and would be considerably busier in production.

The recommendation is therefore a `Reason` rather than a tier. The `unusual_wording` branch added to `src/decision/layer.py` already fires in exactly this range, and its wording should convey that the listing does not contain enough information to assess, rather than implying suspicion. Whether it warrants its own tier cannot be determined without real submission data, and that is recorded as an open question rather than answered from a corpus that cannot speak to it.

#### Why this section exists at all

This defect was visible in the EDA, survived model selection, five-fold grouped cross-validation, calibration analysis and a clean holdout evaluation. It was found by pasting a short job advert into the deployed prediction path and reading the number.

The investigation then took two wrong turns before arriving at the right answer, and each wrong turn was eliminated by a measurement rather than by argument. The feature engineering was exonerated by removing it; the vectoriser was exonerated by disabling sublinear scaling; length itself was exonerated by padding with repetition.

**Validation metrics measure what the corpus contains, not what the product receives.** Every number in Parts 22 to 26 is computed on complete scraped adverts, and no metric computed on that corpus can detect a problem with short pasted text, because the corpus contains none. The mitigation is to probe the deployed path with input that resembles real submissions, and to treat a surprising probe result as a hypothesis to test rather than a conclusion to act on.
"""


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("notebook")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.notebook, encoding="utf-8") as fh:
        nb = json.load(fh)
    cells = nb["cells"]

    hits = [i for i, c in enumerate(cells)
            if c["cell_type"] == "markdown" and "### 27.4 Findings" in "".join(c["source"])]
    if len(hits) != 1:
        raise SystemExit(f"FAILED: found {len(hits)} cells matching 27.4 Findings")
    i = hits[0]
    if "Complete from the results above" not in "".join(cells[i]["source"]):
        raise SystemExit("FAILED: 27.4 is not the placeholder; inspect before overwriting.")

    cells[i] = md(FINDINGS)
    print(f"  - cell {i}: 27.4 Findings written")

    if args.dry_run:
        print("\nDry run, nothing written.")
        return

    shutil.copy2(args.notebook, args.notebook + ".bak")
    with open(args.notebook, "w", encoding="utf-8") as fh:
        json.dump(nb, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"\nWritten. Backup at {args.notebook}.bak")
    print("Markdown only: execution counts and outputs are unchanged.")


if __name__ == "__main__":
    main()
