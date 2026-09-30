# Hakiki Hire

**Verify the job before you apply.**

Hakiki Hire is a hybrid machine learning, rules, and entity-verification system that helps Kenyan job seekers assess job advertisements before applying, paying fees, sharing personal documents, or travelling.

The system also provides authenticated government reviewers with a workflow for investigating referred postings, recording decisions, and maintaining an audit trail.

Capstone project, Group 2, Data Science.

---

## Live demonstration

| Component | Link |
| --- | --- |
| Job seeker interface | https://hakikihire.vercel.app |
| Government review dashboard | https://hakiki-hire-government.onrender.com |
| API | https://job-scam-api-vbc3.onrender.com |
| API documentation | https://job-scam-api-vbc3.onrender.com/docs |

The services use free hosting tiers. The Render services may stop after a period of inactivity, so the first request after a pause can take longer while the service restarts.

---

## 1. Problem statement

Kenyan job seekers have few reliable, real-time ways to check whether a job posting or recruitment agency is legitimate before they apply, pay a fee, provide personal documents, or travel.

Enforcement against fraudulent recruiters is often reactive. Agencies may be investigated, delisted, or blacklisted only after victims have already reported financial loss or other harm. Fake overseas placements are especially serious because the consequences can extend beyond financial loss to passport retention, forced labour, contract substitution, and trafficking.

Verification information is also disconnected from the channels where job seekers encounter postings, including job boards, social media, messaging groups, and forwarded documents.

Hakiki Hire provides a pre-application assessment and routes concerning cases into a review workflow.

---

## 2. What the system does

A job seeker can submit a posting through:

- pasted text,
- a public link,
- or an uploaded PDF, DOCX, or TXT document.

The system returns:

- a content-risk level,
- an independent verification status for the employer or recruitment agency,
- a fraud-risk probability from the trained model,
- human-readable reasons,
- a recommended action,
- and, where appropriate, a referral to the government review queue.

The system is a decision-support tool. It does not make legal determinations, guarantee safety, or replace the authority of a regulator.

---

## 3. Why two statuses are reported

Hakiki Hire deliberately keeps content risk and entity verification separate.

| Risk level | Verification status |
| --- | --- |
| `lower_risk` | `verified` |
| `suspicious` | `unverified` |
| `high_risk` | `blacklisted` |
|  | `possible_impersonation` |
|  | `not_applicable` |

This design supports cases that a single score would hide:

- A registered company name can still appear in a fraudulent posting.
- An unknown employer is not automatically fraudulent.
- A blacklisted agency is strong evidence of elevated risk.
- A near-match to a registered name may indicate impersonation rather than verification.

Verification can raise concern, but it never lowers a content-risk result.

The interface uses **Lower risk**, not **Safe**, because no automated system can guarantee that a job opportunity is safe.

---

## 4. System architecture

```text
                 Job seeker submits
             link / text / document
                          |
                          v
                 Content extraction
       title, employer, agency, salary, contact,
       location, destination and raw posting text
                          |
        +-----------------+------------------+
        |                 |                  |
        v                 v                  v
   NLP classifier   Rule-based signals   Entity verification
   fraud-risk       fees, urgency,       company registry,
   probability      mobile money,        agency registry,
                    passport risks       blacklist, fuzzy match
        |                 |                  |
        +-----------------+------------------+
                          |
                          v
                   Decision layer
        risk level + verification status + reasons
                          |
            +-------------+-------------+
            |                           |
            v                           v
     Job seeker result          Government review case
                                        |
                                        v
                            Authenticated reviewer decision
                                        |
                                        v
                              Append-only audit trail
```

### Key architectural boundaries

The trained classifier receives raw text and returns a probability. It does not query registries, assign verification status, write review cases, or make legal decisions.

The deterministic rules identify explicit patterns such as:

- upfront fees,
- mobile-money payment requests,
- no-interview claims,
- passport retention,
- contract-on-arrival claims,
- artificial urgency,
- unrealistic income,
- and suspicious contact methods.

Entity verification independently checks the extracted organisation against simulated company and recruitment-agency reference data.

The decision layer combines the three evidence sources into user-facing risk and verification outputs.

---

## 5. Running the project locally

The system has three application components:

1. FastAPI assessment and review API
2. React job seeker interface
3. Streamlit government dashboard

The API should be started first.

### 5.1 Create the Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For Conda:

```bash
conda create -n hakiki-hire python=3.12
conda activate hakiki-hire
pip install -r requirements.txt
```

### 5.2 Configure local environment variables

Reviewer authentication requires a JWT signing secret.

```bash
export JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
```

Local development uses SQLite by default. Set `DATABASE_URL` only when a different database is required.

### 5.3 Start the API

```bash
python -m uvicorn src.api.main:app --reload
```

The API runs at `http://127.0.0.1:8000`, with interactive documentation at `/docs`.

Check service and model status:

```bash
curl http://127.0.0.1:8000/api/health
```

A correctly loaded production model reports:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "model": "trained"
}
```

If the trained artefact cannot be loaded, the application falls back to a clearly identified development stub so integration work is not blocked. Stub output must not be presented as trained-model output.

### 5.4 Start the job seeker interface

In a second terminal:

```bash
cd app/jobseeker
npm install
npm run dev
```

The interface runs at `http://localhost:5173`.

The frontend reads the API base URL from `VITE_API_URL`, with a local-development fallback.

### 5.5 Seed a dashboard administrator

Interactive local setup:

```bash
python scripts/seed_admin.py
```

Non-interactive setup:

```bash
export ADMIN_USERNAME="admin"
export ADMIN_DISPLAY_NAME="Hakiki Hire Administrator"
export ADMIN_PASSWORD="use-a-strong-password"

python scripts/seed_admin.py --non-interactive

unset ADMIN_USERNAME
unset ADMIN_DISPLAY_NAME
unset ADMIN_PASSWORD
```

The password must contain at least 12 characters.

### 5.6 Start the government dashboard

In another terminal:

```bash
streamlit run app/government/app.py
```

Use the dashboard's local API option when the FastAPI service is running locally.

### 5.7 Run the tests

```bash
export JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
python -m pytest tests/ -q
```

Current validation: 122 passed.

To treat deprecation warnings as failures:

```bash
python -m pytest tests/ -q -W error::DeprecationWarning
```

---

## 6. API overview

### Public assessment endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/analyse` | Assess pasted text or a public link |
| `POST` | `/api/analyse/file` | Assess a PDF, DOCX, or TXT document |
| `GET` | `/api/analyse/formats` | Retrieve supported upload formats and limits |
| `GET` | `/api/health` | Retrieve service, threshold, and model status |

### Authentication endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/auth/login` | Authenticate a government reviewer |
| `GET` | `/api/auth/me` | Retrieve the authenticated reviewer profile |
| `GET` | `/api/auth/users` | List dashboard users, subject to role checks |
| `POST` | `/api/auth/users` | Create a reviewer account |
| `PATCH` | `/api/auth/users/{id}/status` | Activate or deactivate a user |
| `PATCH` | `/api/auth/users/{id}/role` | Update a user role |

### Protected review endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/cases` | Retrieve and filter the review queue |
| `GET` | `/api/cases/stats` | Retrieve dashboard summary totals |
| `GET` | `/api/cases/{id}` | Retrieve case details and audit history |
| `POST` | `/api/cases/{id}/decision` | Record an authenticated reviewer decision |

The job seeker does not communicate directly with the dashboard. Referred assessments are written to PostgreSQL by the API, and the authenticated dashboard reads those same records through protected API endpoints.

Full endpoint details are available in [docs/api.md](docs/api.md).

The model integration contract is documented in [docs/model_contract.md](docs/model_contract.md).

---

## 7. Input handling and validation

### Pasted text

Pasted text is the most reliable input route because scam postings frequently circulate through messaging platforms without a stable public link.

A minimum character threshold prevents extremely short text from receiving a full assessment. The paste route remains intentionally permissive because a genuine forwarded advert may be short or informally written.

### Public links

The API performs a best-effort HTTP fetch, removes common navigation and script elements, and checks whether the retrieved content resembles a job listing.

Login walls, bot checks, consent pages, dashboards, and unrelated articles are rejected rather than assessed.

Some websites block automated access or render listing content only after JavaScript execution. In those situations, the user is asked to paste the listing text.

### Uploaded documents

The upload route accepts PDF, DOCX, and TXT.

Uploads are checked for file type, size, readable text, minimum content length, and job-listing vocabulary.

Scanned images and image-only PDFs require optical character recognition, which is not included in the current version.

---

## 8. Modelling and data

### 8.1 Data sources

| Layer | Source | Role |
| --- | --- | --- |
| Real labelled fraud data | EMSCAD | Core supervised modelling and real holdout |
| Kenyan postings | BrighterMonday, Fuzu, JobWeb Kenya, Corporate Staffing, PigiaMe | Local language, formats, salary patterns, and annotation pool |
| Synthetic scenarios | Generated Kenyan job-scam examples | Training supplement and system test scenarios |
| Verification references | Simulated company registry, agency registry, and blacklist | Entity verification at request time |

Real job-board postings are not automatically treated as verified legitimate examples. Their source provenance and label confidence remain distinct from confirmed labels.

### 8.2 Provenance partitions

The merged corpus contains **71,280 records** after exact and normalized-text deduplication.

| Partition | Rows | Role |
| --- | ---: | --- |
| Real labelled (EMSCAD) | 15,537 | Supervised modelling, validation, and holdout |
| Synthetic scenarios | 42,688 | Evaluated as a training supplement, see 8.9 |
| Kenyan unlabelled | 13,055 | Local analysis and future manual annotation |

Partitioning is performed inside the modelling notebook rather than by a separate script. An earlier workflow pre-computed partitions with `scripts/build_splits.py`; that script has been removed because splitting a corpus before deciding what belongs in it fixed a decision that later evidence changed.

Validation and holdout are drawn **exclusively from real EMSCAD rows**, which are split before synthetic data is considered. Synthetic rows can therefore only ever enter training, which makes contamination structurally impossible rather than merely checked for.
### 8.3 Fingerprint isolation

The original data preparation removed exact duplicates, but normalized-text review found additional near-identical postings.

The final modelling workflow creates a fingerprint from normalized title, description, and requirements. Text is lowercased, punctuation is removed, whitespace is normalized, and a stable MD5 hash is generated.

Real training, validation, and holdout partitions are checked to ensure no fingerprints are shared across partitions.

This prevents the model from being evaluated on a normalized copy of a posting it saw during training.

### 8.4 Binary modelling target

The merged dataset retains three descriptive classes during data understanding:

- Legitimate
- Suspicious
- Fraudulent

For modelling, Suspicious and Fraudulent are combined into one **Fraud-risk** positive class.

The deployed classifier therefore returns a binary fraud-risk probability. The application's three user-facing risk tiers are assigned later by the decision layer.

### 8.5 Model pipeline

The deployed artefact is a single scikit-learn `Pipeline` that accepts a list of raw strings.

The pipeline combines TF-IDF features over unigrams and bigrams with six numeric features derived from the text alone:

| Feature | Description |
| --- | --- |
| `urls_per_100w` | URL count, normalised per 100 words |
| `emails_per_100w` | Email address count per 100 words |
| `phones_per_100w` | Telephone number count per 100 words |
| `uppercase_ratio` | Shouting, as a share of words |
| `digit_ratio` | Digits as a share of characters |
| `mean_word_length` | Separates terse informal wording from advert prose |

Every numeric feature is a **rate rather than a count**. An earlier revision used raw `text_length`, `word_count` and raw contact counts; those were replaced because a feature that grows with posting length has no fraud interpretation, only a corpus-specific correlation. See section 8.9.

No missing-field indicators are used. Absence of a company name records how a posting was submitted rather than whether it is fraudulent, and does not generalise across ingestion channels: a pasted message lacks a company field whether or not it is a scam.

The reusable transformer lives in `src/models/feature_builder.py`. It is imported rather than defined in the notebook, because joblib serialises a class by import path and a notebook-local definition fails to load inside the API.

The exported model lives at `artifacts/model.pkl`.

Current model version: `logreg-hybrid-v5-density-20260929`

Configuration: `C=10.0`, `class_weight="balanced"`, uncapped TF-IDF vocabulary (260,884 terms), trained on 13,206 real EMSCAD postings.

The model was exported with scikit-learn `1.9.0`, and the same version is pinned in `requirements.txt` to prevent serialised-model incompatibility.
### 8.6 Model comparison

All models were trained on real EMSCAD data and scored on the same real validation set of 2,331 postings.

| Model | Validation PR-AUC | Validation ROC-AUC | Brier |
| --- | ---: | ---: | ---: |
| Majority class | `0.0438` | n/a | `0.0438` |
| Rule engine alone | `0.0498` | `0.5155` | `0.0443` |
| Logistic regression (tuned, raw-count features) | `0.7987` | `0.9558` | `0.0168` |
| **Logistic regression (tuned, density features, deployed)** | **`0.7906`** | **`0.9544`** | **`0.0174`** |
| Linear SVM (calibrated) | `0.7909` | `0.9479` | `0.0166` |
| Rules combined with logistic regression | `0.7921` | `0.9504` | `0.0173` |
| Gradient boosting (SVD-reduced text) | `0.6324` | `0.9063` | `0.0262` |
| DistilBERT (fine-tuned, 3 epochs) | `0.6866` | `0.9380` | `0.0274` |
| Frozen sentence embeddings with linear head | `0.5307` | `0.8894` | `0.0281` |
| Zero-shot embedding similarity | `0.0998` | `0.4586` | n/a |

The deployed model trades 0.0081 validation PR-AUC for length-invariant features, and catches one more fraudulent holdout posting than the raw-count version. See section 8.9.

Logistic regression was selected over the calibrated linear SVM, which scores within 0.001 PR-AUC of it, because it returns a probability directly, supports threshold tuning, and remains interpretable through per-term coefficients, which the decision layer requires in order to explain itself.

**The rule engine's score is not a measurement of the rules.** It fires on only 6.91% of EMSCAD postings, and the Kenya-specific rules on three or four postings each out of 2,331. EMSCAD is a United States corpus collected between 2012 and 2014 and contains almost no M-Pesa, till number, or Gulf placement vocabulary, so the rules sit at chance by construction. On this corpus they change no decisions at the operating threshold.

Tuning contributed `+0.0344` PR-AUC over the previously deployed configuration refitted on the same data.
### 8.7 Corrected evaluation

An earlier hybrid-model path reintroduced holdout rows into training through a second split. The workflow was corrected, all components refitted, and the inflated metrics retired. Splitting is now grouped on a normalized-text fingerprint with assertions that no fingerprint appears in more than one partition.

The holdout is 2,331 unseen real EMSCAD postings, `4.89%` fraudulent. At the selected threshold of `0.25`:

| Metric | Value |
| --- | ---: |
| PR-AUC | `0.8071` |
| ROC-AUC | `0.9685` |
| Brier | `0.0189` |
| Recall | `0.8158` |
| Precision | `0.6327` |
| Confusion matrix | `[[2163, 54], [21, 93]]` |

At this operating threshold:

- 93 of 114 Fraud-risk postings were detected.
- 21 of 114 Fraud-risk postings were missed.
- 54 legitimate postings were flagged for review, which is `6.3%` of submissions.

**The holdout score exceeds the validation score** (`0.8071` against `0.7906` PR-AUC), which indicates the selection process did not overfit. Every hyperparameter, calibration decision and threshold was chosen on training and validation data.

The hardest misses are instructive. In the validation error analysis, the lowest-scoring fraudulent postings were ordinary corporate adverts containing no fee demand, no payment instruction and no unusual urgency, scored between 0.006 and 0.053 by every model tested including the fine-tuned transformer. EMSCAD labels many postings fraudulent on the basis of the employer behind them rather than the wording in front of them, which no text classifier can recover from text alone. **This is the empirical case for entity verification as a distinct component rather than a supplementary feature.**
### 8.8 Threshold trade-off

The operating threshold is selected from an explicit cost asymmetry rather than inherited. A missed scam typically means a job seeker pays a fee they cannot recover; a false alarm costs a reviewer's time and routes the case to a person rather than blocking it.

Validation sweep:

| Threshold | Recall | Precision | Caught | Missed | False alarms |
| --- | ---: | ---: | ---: | ---: | ---: |
| `0.35` (previous) | `0.706` | `0.818` | 72 | 30 | 16 |
| **`0.25` (selected)** | **`0.775`** | **`0.658`** | **79** | **23** | **41** |
| `0.20` | `0.784` | `0.548` | 80 | 22 | 66 |
| `0.17` | `0.814` | `0.449` | 83 | 19 | 102 |
| `0.10` | `0.843` | `0.337` | 86 | 16 | 169 |

The sweep was computed on the raw-count model before the density retrain in section 8.9. The selected threshold was re-checked on the deployed density model at holdout evaluation (section 8.7).

Moving from `0.35` to `0.25` catches seven more fraudulent postings for 25 additional reviews, a trade of roughly 3.6 reviews per additional detection. Minimum expected cost at both a 5x and a 10x penalty for a missed scam over a false alarm selects `0.26`, as does maximum F2. Going further to `0.17` costs roughly 15 reviews per additional detection.

`high_risk_threshold` remains `0.70`, where precision is `0.967`. That tier tells a government reviewer a posting is high risk and should be close to certain.

Both thresholds live in `src/core/config.py` and are pinned by a test, because the decision layer has behaviour keyed to `suspicious_threshold` beyond simple tiering. The model and the thresholds must be changed together.

Calibration was evaluated and **not** applied. Sigmoid and isotonic calibration both moved the mean prediction closer to the true positive rate while making Brier score and PR-AUC worse, because shrinking scores toward the base rate costs more on confidently correct fraud cases than it recovers elsewhere.

The canonical modelling notebook is `notebooks/02_job_scam_detection.ipynb`.

### 8.9 Experiments that changed the design

Three findings reversed a working assumption. Each is recorded because the reasoning is reusable, and because a negative result obtained properly is a result.

#### Synthetic training data was excluded

Adding all 42,688 synthetic rows to training **reduces** real-data PR-AUC by `0.119`. Measured across five re-drawn splits, arm B lost on every one; paired `t(4) = -4.54`, `p = 0.011`.

The synthetic corpus contributes 1,842 unique terms across 42,688 rows, and `98.55%` of its vocabulary already appears in real postings. It is a small subset of real job-advert language rather than a different language, so it adds almost no lexical coverage while heavily reweighting TF-IDF document frequencies for the postings the system has to score. Word frequencies confirm fixed templates: `work` and `preferred` each occur exactly 11,426 times in the Suspicious class, which is exactly the number of Suspicious rows from that generator.

The synthetic data does carry genuine Kenya-specific fraud vocabulary, which the real corpus lacks entirely. Its template structure costs more than that vocabulary is worth, so it is excluded from training and the gap is covered by the deterministic rule layer.

#### Transfer learning was evaluated and declined

Three levels of cost: zero-shot embedding similarity, frozen sentence embeddings with a linear head, and a full DistilBERT fine-tune on a GPU.

The fine-tune produced the **largest Kenyan probe separation of any model tested** (`+0.817`), scoring an explicit M-Pesa registration-fee demand at `0.966` on a corpus containing no M-Pesa postings. It nevertheless loses on measured data (`0.6866` against `0.7987` PR-AUC) and triples the false alarm count at the same threshold.

Not deployed. The deficit is measured on 2,331 real postings while the gain is measured on six hand-written probes; the decision layer owes job seekers explainable reasons that a transformer does not provide; and `torch` plus `transformers` would substantially change the deployment footprint. The fine-tune is the strongest available evidence that a labelled Kenyan corpus would materially improve the system, which makes it future work rather than a reason to change the deployment now.

The training procedure is versioned at `notebooks/colab_distilbert_finetune.ipynb`.

#### A suspected length artefact was disproved

The same legitimate advert scored `0.575` truncated to 28 characters and `0.196` at 462, and `text_length` carried the largest negative coefficient of any numeric feature. The EDA had already flagged that EMSCAD legitimate postings average 631 characters against 283 for fraudulent ones.

Length-invariant features did not fix it. Nor did removing the numeric block entirely, nor disabling sublinear TF-IDF scaling. Padding a posting with **repetitions of its own text** moved the score by `0.002` across a sixfold length increase, which exonerated length conclusively. The original test had varied *evidence* across its truncations and attributed the result to *length*: the score step falls exactly where the posting first mentions professional qualifications.

The density feature set was kept regardless, on principle and on holdout recall (`81.6%` against `80.7%`).

### 8.10 Known model vulnerability: vocabulary dilution

Appending vocabulary a posting did not previously contain reduces the TF-IDF weight on **every term it did contain**, because the vectors are L2-normalised. Repetition does not do this; novel vocabulary does.

| Variant | Words | Score |
| --- | ---: | ---: |
| Bare scam posting | 16 | `0.310` |
| Repeated verbatim six times | 96 | `0.308` |
| Padded with three sentences of neutral prose | 37 | `0.158` |
| Padded with six sentences of neutral prose | 58 | `0.130` |

Measured on all 114 fraudulent holdout postings, appending three sentences of ordinary corporate prose moves **seven from detected to missed**, reducing recall from `81.6%` to `75.4%`.

The effect scales with how much new vocabulary is added relative to what the posting already contains, so **short postings are the most vulnerable**, and short pasted messages are this system's primary input.

The deterministic rule layer is the mitigation: regular expressions match regardless of surrounding text, so a diluted fee demand still fires `upfront_fee` and `mobile_money`, and two strong signals force high risk independent of the classifier. On EMSCAD the blend recovers only one of the seven, because the rules are near-inert on that corpus; on Kenyan traffic it would recover most of them.

Recorded as a known limitation rather than fixed. Removing L2 normalisation would reintroduce genuine length sensitivity, sliding-window scoring multiplies inference cost, and weighting rule hits more heavily on disagreement erodes the independence between content risk and rule signals that the decision layer is built around. No candidate mitigation could be validated on a corpus where the mitigating component fires on 6.91% of postings.
## 9. Verification data

Verification uses versioned demonstration data from `data/external/`.

The reference layer currently includes:

- 60 company records,
- 25 recruitment-agency records,
- blacklist records for names, email addresses, domains, and telephone numbers.

Every reference entry is marked `record_is_mock = true`.

The registries demonstrate the verification architecture and are not official government records.

### Verification rules

- Registry absence is not proof of fraud.
- Registry presence is not proof that a particular advert is legitimate.
- A blacklisted entity raises the assessment.
- A similar but unequal organisation name may indicate impersonation.
- Direct employers and recruitment agencies are checked against different reference sets.

---

## 10. Government review workflow

Assessments are referred when risk, verification, or rule evidence justifies human attention.

A referred case stores the normalized posting, organisation identity, fraud-risk probability, risk level, verification status, reason codes, model version, creation time, review status, and audit entries.

Government reviewers authenticate using JWT-based access tokens.

Reviewer decisions are attributed to the authenticated user and appended to the audit trail. The audit trail preserves both the original system referral and subsequent human action.

Reviewed outcomes may later support a versioned retraining dataset, but a reviewer decision does not automatically retrain the model. Retraining remains a deliberate, separately evaluated process.

---

## 11. Deployment

| Component | Platform |
| --- | --- |
| Job seeker interface | Vercel |
| API | Render |
| Government dashboard | Render |
| Database | Render PostgreSQL |

Deployment configuration is versioned in `render.yaml`.

Detailed instructions are available in [docs/DEPLOY.md](docs/DEPLOY.md).

### Important environment variables

| Variable | Service | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | API | PostgreSQL connection string |
| `JWT_SECRET_KEY` | API | Reviewer-token signing secret |
| `CORS_ORIGINS` | API | Permitted browser origins |
| `VITE_API_URL` | Vercel | API base URL embedded into the frontend build |
| `HAKIKI_HIRE_API_BASE_URL` | Dashboard | Hosted API address |
| `ADMIN_USERNAME` | Admin seeding | Initial administrator username |
| `ADMIN_DISPLAY_NAME` | Admin seeding | Initial administrator display name |
| `ADMIN_PASSWORD` | Admin seeding | Initial administrator password |

Secrets must be supplied through host environment settings. They must not be committed to the repository.

---

## 12. Repository structure

```
job-scam-detection/
  app/
    jobseeker/              React and Vite public interface
    government/             Streamlit government dashboard
  artifacts/
    model.pkl               Versioned deployed model pipeline
  data/
    raw/                    Source data, not committed
    processed/              Reproducible outputs, not committed
    external/               Simulated verification reference data
    synthetic/              Generated scenario data
  docs/
    DEPLOY.md               Deployment instructions
    api.md                  API documentation
    model_contract.md       Model integration contract
    architecture/           System design documentation
    diagrams/               Wireframes and visual designs
    meeting_notes/          Decisions and supervisor feedback
  notebooks/
    02_job_scam_detection.ipynb        Canonical: preparation, EDA, modelling
    00_legacy_end_to_end_reference.ipynb   Superseded, retained for comparison
    colab_distilbert_finetune.ipynb    GPU fine-tune companion, see 8.9
  scripts/
    seed_admin.py
  src/
    api/                    FastAPI routes and authentication
    core/                   Configuration and shared schemas
    data/                   Loading and cleaning
    db/                     Database models and sessions
    decision/               Evidence combination and referral
    explainability/         Human-readable explanations
    features/               Feature engineering
    ingestion/              Text, URL, and document extraction
    models/                 Classifier and feature builder
    rules/                  Deterministic scam-pattern rules
    verification/           Registry and blacklist checks
  tests/
  tools/                    Notebook review tooling
  CONTRIBUTING.md
  README.md
  render.yaml
  requirements.txt
```

Large datasets, local databases, environment files, caches, and credentials are excluded from version control.
## 13. Contribution workflow

New work must branch from the latest `main`.

Branch format:

```text
<type>/<short-description>-<firstname>
```

Examples:

```text
feature/government-dashboard-briannah
fix/url-ingestion-alex
docs/deployment-christopher
data/schema-cleaning-melisa
```

Before committing:

```bash
git branch --show-current
git status --short
python -m pytest tests/ -q
```

Commit prefixes: `feat:` `fix:` `docs:` `data:` `refactor:` `test:` `chore:`

Full workflow and file-placement rules are documented in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 14. Team and ownership

| Area | Owner | Status |
| --- | --- | --- |
| Dataset search | Whole team | Complete |
| Data loading and cleaning | Melisa Achieng | Complete |
| Data audit | Briannah Chelangat | Complete |
| Exploratory data analysis | Christopher Kariuki | Complete |
| Model development | Cleopas Karanja, Melisa Achieng, Alex Kinyua | Complete |
| Model integration and validation | Alex Kinyua, Cleopas Karanja, Melisa Achieng | Complete |
| API and backend | Alex Kinyua, Briannah Chelangat | Complete |
| Job seeker interface | Alex Kinyua | Complete |
| Government dashboard and authentication | Briannah Chelangat | Complete |
| Repository administration | Alex Kinyua | Ongoing |
| Project documentation | Christopher Kariuki | Ongoing |
| Deployment | Alex Kinyua, Briannah Chelangat | Complete |

Task tracking is managed in ClickUp. Group lead: Cleopas Karanja.

---

## 15. Current project status

### Complete

- Data collection and integration
- Provenance-based data partitioning
- Fingerprint-based modelling isolation
- Binary fraud-risk classifier
- Deterministic scam-pattern rules
- Simulated entity verification
- Fuzzy impersonation detection
- Text, URL, PDF, DOCX, and TXT ingestion
- Job seeker interface
- FastAPI service
- PostgreSQL persistence
- Review-case routing
- JWT reviewer authentication
- User administration endpoints
- Government review dashboard
- Reviewer decisions and audit trail
- Vercel and Render deployment
- Automated tests
- Final documentation metric corrections
- Model development, completed after a change in team ownership, including a synthetic-data experiment, transfer-learning evaluation, threshold selection, and model export

### Finalization

- End-to-end production validation
- Final presentation metric corrections
- Group rehearsal and demonstration preparation

---

## 16. Known limitations

- The real labelled modelling data originates from a foreign corpus.
- Kenya-specific fraud patterns are partly covered by deterministic rules rather than learned from locally confirmed examples.
- No public, labelled Kenyan job-scam dataset was identified.
- The current Kenyan posting collection remains an annotation pool rather than ground-truth evaluation data.
- At the selected model threshold, 21 of 114 real Fraud-risk holdout postings were missed.
- Synthetic training records were measured to reduce real-data performance and are excluded from training. See section 8.9.
- Appending unrelated vocabulary to a posting weakens the classifier signal. See section 8.10.
- Registry and blacklist records are simulated.
- Automated link extraction does not work for every site, especially login-protected, bot-protected, or JavaScript-rendered pages.
- Optical character recognition is not included for screenshots or image-only documents.
- Document-type classification is limited to heuristic checks.
- The project does not integrate with a live government registry.
- The free hosting services may experience startup delays after inactivity.
- Registry administration through the dashboard is future work.
- Automatic model retraining is deliberately not implemented.

---

## 17. Future work

Potential extensions include:

- manual annotation of Kenyan postings,
- local model evaluation,
- optical character recognition,
- document-type classification,
- live registry integration,
- audited registry management,
- repeat-entity and campaign clustering,
- regulator-configurable escalation policies,
- model monitoring and drift detection,
- versioned retraining datasets,
- scheduled backup and migration management,
- WhatsApp and USSD access,
- and structured user testing with job seekers and reviewers.
- mitigation of vocabulary dilution (section 8.10),
- an ensemble of the linear model and the fine-tuned transformer, whose failures overlapped by only 50%,

---

## 18. Disclaimer

Hakiki Hire is a student capstone project.

Registry and blacklist data are simulated. Model outputs are advisory and must not be treated as an official verification, legal determination, or guarantee concerning any employer, recruitment agency, individual, or job posting.