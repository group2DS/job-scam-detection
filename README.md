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

Current validation: 71 passed.

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

The merged corpus contains 68,138 records after normalized-text deduplication.

| Partition | Rows | Role |
| --- | ---: | --- |
| Real labelled | 15,555 | Supervised modelling and isolated evaluation |
| Synthetic scenarios | 39,527 | Training supplement and scenario testing |
| Kenyan unlabelled | 13,056 | Local analysis and future manual annotation |

The partitions can be regenerated with:

```bash
python scripts/build_splits.py path/to/final_job_spam_dataset.csv
```

The large CSV outputs are not committed. The script provides a reproducible transformation from the merged dataset.

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

The deployed artefact is a single scikit-learn Pipeline that accepts raw text.

The pipeline includes TF-IDF features using unigrams and bigrams, text length, word count, URL count, email count, phone-number count, uppercase-token count, feature scaling, and Logistic Regression.

The reusable structured-text transformer lives in `src/models/feature_builder.py`.

The exported model lives at `artifacts/model.pkl`.

Current model version: `logreg-hybrid-v3-clean-split`

The model was exported with scikit-learn `1.9.0`, and the same version is pinned in `requirements.txt` to prevent serialized-model incompatibility.

### 8.6 Model comparison

| Model | Validation ROC-AUC | Validation PR-AUC |
| --- | ---: | ---: |
| TF-IDF Logistic Regression baseline | `0.9057` | `0.6199` |
| Hybrid LinearSVC | | `0.7386` |
| Hybrid Logistic Regression | Selected for deployment | Selected for deployment |

Hybrid Logistic Regression was selected because it provides probability output directly, supports threshold tuning, remains interpretable through coefficients, works well with sparse text features, and integrates cleanly into the deployed raw-text pipeline.

### 8.7 Corrected evaluation

Final review identified that an earlier hybrid-model path had reintroduced holdout rows into training through a second split. The workflow was corrected, all modelling components were refitted, and the previous inflated metrics were retired.

At the validation-selected threshold of `0.35`, the corrected real holdout results are:

| Metric | Value |
| --- | ---: |
| Precision | `0.7619` |
| Recall | `0.4812` |
| F1 | `0.5899` |
| ROC-AUC | `0.9214` |
| PR-AUC | `0.6676` |
| Confusion matrix | `[[2958, 20], [69, 64]]` |

At this operating threshold:

- 64 of 133 Fraud-risk postings were detected.
- 69 of 133 Fraud-risk postings were missed.
- 20 legitimate postings were incorrectly flagged.

The result demonstrates useful ranking ability but insufficient standalone recall. This is why Hakiki Hire combines the model with deterministic scam-pattern rules, registry checks, transparent reasons, and human review.

### 8.8 Threshold trade-off

Post hoc diagnostics show the trade-off between fraud recall and false alerts:

| Threshold | Recall | Precision |
| --- | ---: | ---: |
| `0.35` | `0.4812` | `0.7619` |
| `0.30` | `0.5865` | `0.7027` |
| `0.20` | `0.7218` | `0.4800` |
| `0.10` | `0.8496` | `0.2062` |

These holdout diagnostics were not used for model fitting, hyperparameter tuning, or threshold selection.

The application's warning and escalation tiers remain configurable separately from the model training process.

The canonical modelling notebook is `notebooks/01_job_scam_detection.ipynb`.

---

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

```text
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
    01_job_scam_detection.ipynb
    03_modelling_integration.ipynb
  scripts/
    build_splits.py
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
  CONTRIBUTING.md
  README.md
  render.yaml
  requirements.txt
```

Large datasets, local databases, environment files, caches, and credentials are excluded from version control.

---

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
| Model development | Cleopas Karanja, Melisa Achieng | Complete |
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

### Finalization

- End-to-end production validation
- Final documentation metric corrections
- Final presentation metric corrections
- Group rehearsal and demonstration preparation

---

## 16. Known limitations

- The real labelled modelling data originates from a foreign corpus.
- Kenya-specific fraud patterns are partly covered by deterministic rules rather than learned from locally confirmed examples.
- No public, labelled Kenyan job-scam dataset was identified.
- The current Kenyan posting collection remains an annotation pool rather than ground-truth evaluation data.
- At the selected model threshold, 69 of 133 real Fraud-risk holdout postings were missed.
- Synthetic training records can introduce generator-specific vocabulary into feature coefficients.
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

---

## 18. Disclaimer

Hakiki Hire is a student capstone project.

Registry and blacklist data are simulated. Model outputs are advisory and must not be treated as an official verification, legal determination, or guarantee concerning any employer, recruitment agency, individual, or job posting.