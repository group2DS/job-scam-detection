# AI-Powered Job Scam Detection System

A hybrid machine learning and verification system that helps Kenyan job seekers assess whether a job posting is likely to be fraudulent, and gives government reviewers a workflow for triaging suspicious postings and recruitment entities.

Capstone project, Group 2, Data Science.

---

## 1. Problem statement

Kenyan job seekers have very few reliable, real time ways to check whether a job posting or recruitment agency is legitimate before they apply, pay a fee, hand over personal documents, or travel. Enforcement against fraudulent agencies is largely reactive: agencies are investigated, delisted, or blacklisted only after victims have already come forward. Fake overseas placements are the most severe case, because the harm can extend from financial loss to forced labour and trafficking.

The verification information that does exist is disconnected from the channels where job seekers actually encounter postings: job boards, social media, and WhatsApp groups.

## 2. What this system does

The system accepts a job posting as a link, pasted text, or an uploaded document, and returns:

- a risk level,
- a verification status for the employer or recruitment agency,
- a plain language explanation of which signals drove the result,
- a recommended action for the job seeker,
- and, where appropriate, a referral into a government review queue.

It is a decision support tool. It does not make legal determinations and it does not replace any regulator's authority.

## 3. Running it locally

Two services. The API must be started first.

### API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m uvicorn src.api.main:app --reload
```

Runs on `http://127.0.0.1:8000`, with interactive documentation at `/docs`.

The service starts whether or not a trained model is present. When `artifacts/model.pkl` is absent it falls back to a clearly identified keyword stub, so interface work is never blocked on modelling. Check which is active:

```bash
curl http://127.0.0.1:8000/api/health
```

### Job seeker interface

```bash
cd app/jobseeker
npm install
npm run dev
```

Runs on `http://localhost:5173`. The API's CORS settings already allow that origin.

### Tests

```bash
python -m pytest tests/ -q
```

23 tests, no services required.

## 4. Users

**Job seekers.** Primary beneficiaries. They receive an advisory result before applying, paying, or travelling. The system informs a decision they still make themselves.

**Government reviewers.** They receive ambiguous and high risk cases, confirm or dismiss them, and build up a record of repeat entities and emerging scam patterns.

## 5. Architecture

```
                 Job seeker submits
             URL / pasted text / document
                          |
                          v
                 Content extraction
       title, employer, agency, salary, contact,
        location, destination, fees, contract
                          |
        +-----------------+------------------+
        |                 |                  |
        v                 v                  v
   NLP classifier   Rule based signals   Entity verification
   content risk     fees, urgency,       company registry,
   probability      vague duties         agency registry,
                                         blacklist, fuzzy match
        |                 |                  |
        +-----------------+------------------+
                          |
                          v
                   Decision layer
        risk level + verification status + reasons
                          |
            +-------------+-------------+
            v                           v
     Job seeker result          Government review queue
                                        |
                                        v
                                  Human decision
                                        |
                                        v
                            Audit trail + retraining pool
```

The classifier receives text and returns a probability. It never sees registry data and never assigns a tier. Verification is computed independently, and the decision layer combines the two. That boundary is why a registered employer can still be flagged high risk, and why modelling can iterate without touching the API.

Two statuses are returned, never collapsed into one:

| Risk level | Verification status |
| --- | --- |
| `lower_risk` | `verified` |
| `suspicious` | `unverified` |
| `high_risk` | `blacklisted` |
| | `possible_impersonation` |
| | `not_applicable` |

Guiding rules:

- Not found in a registry does not mean fraudulent.
- Found in a registry does not mean safe.
- Blacklisted is strong high risk evidence.
- A near miss on a registered name is a possible impersonation, not a match.

The word "safe" is never used in the interface. The lowest tier reads "Lower risk", because the system cannot guarantee safety.

## 6. API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/analyse` | Assess a listing from a URL or pasted text |
| POST | `/api/analyse/file` | Assess a listing from a PDF, DOCX or TXT upload |
| GET | `/api/analyse/formats` | Supported upload formats and limits |
| GET | `/api/cases` | Review queue, filterable by risk, status, market |
| GET | `/api/cases/stats` | Dashboard summary counts |
| GET | `/api/cases/{id}` | Case detail including reasons and audit trail |
| POST | `/api/cases/{id}/decision` | Record a reviewer decision |
| GET | `/api/health` | Service status, including stub or trained model |

Referral is a database write. The government dashboard reads the same table the analysis endpoint writes to, so there is no queue or integration layer between them.

Full details in [docs/api.md](docs/api.md). The modelling interface contract is in [docs/model_contract.md](docs/model_contract.md).

## 7. Data

Preference order: real world data first, programmatic generation only where real examples are unavailable.

The merged corpus is 68,138 rows after deduplication, partitioned by provenance rather than pooled. The three splits have different epistemic status and different roles:

| Split | Rows | Role |
| --- | --- | --- |
| `01_trainable_real.csv` | 15,555 | Trains the classifier. Real labelled rows, 4.3% fraud |
| `02_synthetic_scenarios.csv` | 39,527 | System test fixtures. Never training or validation data |
| `03_kenyan_unlabelled.csv` | 13,056 | Local distributions and the manual annotation pool |

Sources:

| Layer | Source | Role |
| --- | --- | --- |
| Labelled fraud data | EMSCAD job postings | Trains the core text classifier |
| Real Kenyan postings | BrighterMonday, Fuzu, JobWeb Kenya, Corporate Staffing, PigiaMe | Local language, formats, salary norms |
| Verification reference | Mock company registry, mock agency registry, blacklist | Entity lookup at request time |
| Scenario testing | Generated Kenyan scam scenarios | Pipeline and interface behaviour tests |

The splits exist because of a measured failure. Training on the pooled dataset produced 0.99 accuracy and 0.9987 ROC-AUC. Trained on the generated rows alone the model scored a perfect 1.000 on held out synthetic data, but caught only 33% of real fraud at 9% precision. Generated and real rows were separable at 100% accuracy, and every generated row fell inside a 286 to 635 character band while real postings ran past 14,000. The honest baseline on real data is approximately 0.65 F1 on the fraud class.

Every record carries provenance so an assumed label is never mistaken for a verified one:

```
source_dataset    EMSCAD | BrighterMonday | Fuzu | JobWebKenya |
                  CorporateStaffing | PigiaMe | MockKenyanScam | HumanReviewed
label_source      original_dataset | platform_assumed_legitimate |
                  synthetic_generation | government_review | manual_annotation
label_confidence  high | medium | low
is_synthetic      true | false
fingerprint       normalised text hash, split on this rather than row index
```

Postings collected from job boards are real postings, not verified legitimate postings. They carry medium confidence, not ground truth.

Registry data is simulated, flagged `record_is_mock`, read from `data/external/` at startup, and labelled as a demonstration source in both interfaces.

### Canonical posting schema

```
posting_id, title, description, company, agency, recruitment_channel,
location, country, is_overseas, salary, currency, employment_type,
email, phone, application_url, source, fraud_label
```

`fraud_label` is a column in the postings table, `0` legitimate and `1` fraudulent. Registries stay as separate lookup tables and are joined at verification time, never appended as posting rows.

The classifier is trained as a binary model. The three risk tiers are produced by the decision layer from thresholds in `src/core/config.py`, so they can be retuned from validation data without retraining anything.

## 8. Repository structure

```
job-scam-detection/
  app/
    jobseeker/       React interface, Vite
    government/      review dashboard
  src/
    api/             FastAPI routes and application entry point
    core/            shared schemas and configuration
    ingestion/       URL, text and document extraction
    models/          classifier wrapper with development stub
    rules/           deterministic scam signal detection
    verification/    registry lookup, fuzzy matching, blacklist
    decision/        combines evidence into tiers and routing
    db/              review cases and audit entries
    data/            loading and cleaning
    features/        feature engineering
    explainability/  reason generation
  data/
    raw/             source data, unmodified
    processed/       cleaned, schema aligned, split by provenance
    external/        registries and reference lookups, versioned
    synthetic/       generated records
  docs/
    api.md           API service documentation
    model_contract.md   modelling export interface
    architecture/    system design
    diagrams/        interface designs and design notes
    meeting_notes/   decisions and supervisor feedback
  notebooks/         exploration and EDA
  artifacts/         trained model artefacts, gitignored
  tests/
```

Large data files are not committed. The three demonstration registry CSVs in `data/external/` are the deliberate exception. See `.gitignore`.

## 9. Working on this repo

Branch from `main`, never commit to `main` directly, open a pull request, get one review.

```
feature/api-skeleton
feature/jobseeker-ui
feature/ui-polish
feature/modelling
feature/dashboard
docs/<topic>
```

Commit prefixes: `feat:` `fix:` `docs:` `data:` `refactor:` `test:` `chore:`

Full contribution rules are in [CONTRIBUTING.md](CONTRIBUTING.md).

## 10. Team and ownership

| Area | Owner | Status |
| --- | --- | --- |
| Dataset search | Whole team | Done |
| Data loading and cleaning | Melisa Achieng | Done |
| Data audit | Briannah Chelangat | Done |
| EDA | Cleopas Karanja | Done |
| Modelling | Cleopas Karanja | In progress |
| API and backend | Alex Kinyua, Brisley Chelangat | Done |
| URL pipeline and job seeker interface | Alex Kinyua, Brisley Chelangat | Done |
| Government dashboard | Brisley Chelangat | In progress |
| README and repository administration | Alex Kinyua | Ongoing |
| Project documentation | Christopher Kariuki | Ongoing |
| Deployment | Unassigned | Not started |

Task tracking is in ClickUp. Group lead: Cleopas Karanja.

## 11. Roadmap

**Phase 1. Data.** Source real data, agree the canonical schema, audit, clean, EDA. *Complete.*

**Phase 2. Interfaces and services.** API, decision pipeline, registry verification, job seeker interface, document upload. *Complete.*

**Phase 3. Modelling.** TF-IDF with Logistic Regression baseline, structured feature comparison, imbalance handling, calibration, explainability. *In progress.*

**Phase 4. Government dashboard.** Queue, case detail, reviewer decisions, audit trail wired to the API. *In progress.*

**Phase 5. Integration.** Model swap, deployment, end to end testing, evaluation write up, panel presentation.

## 12. Scope

**In scope.** Data pipeline and provenance partitioning, baseline and comparison models, imbalance handling, explainability, registry verification against simulated data including fuzzy impersonation matching, job seeker interface with link, paste and document upload, government review dashboard, audit trail.

**Stretch.** Threshold tuning from precision and recall analysis, transformer embeddings, duplicate campaign clustering, manual annotation of Kenyan postings to build a locally labelled set.

**Out of scope, described as future work.** Live integration with any government system, WhatsApp or USSD interfaces, live scraping of job boards, optical character recognition for scanned documents and screenshots, and actual adoption by government or job board partners.

## 13. Evaluation

Fraudulent postings are a small minority, so accuracy alone is not a success measure. Always predicting "legitimate" scores roughly 95% accuracy and 0.000 F1 on the class that matters.

Reported metrics are recall on the fraudulent class, precision and false positive rate, F1, PR-AUC and ROC-AUC, the confusion matrix with false negatives called out explicitly, and a qualitative interpretability check. Real and generated data are evaluated separately. Splits are taken on the text fingerprint rather than the row index, so near duplicate postings cannot straddle the train and test boundary.

## 14. Known limitations

- The system assumes the input is a job listing. An unrelated document still returns an assessment. A document type check is future work.
- Scanned images and screenshots cannot be read, since no optical character recognition is included.
- Registry data is simulated. Absence from it proves nothing about the real world.
- The classifier is trained on a foreign corpus. Kenya specific overseas placement patterns are covered by the deterministic rules rather than learned, until locally annotated data is available.
- No labelled Kenya specific job scam dataset exists publicly, so local fraud examples are limited.

## 15. Disclaimer

This is a student capstone project. Registry data is simulated. Outputs are advisory only and must not be treated as an official verification of any company, agency, or job posting.
