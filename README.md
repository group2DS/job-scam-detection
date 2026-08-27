# AI-Powered Job Scam Detection System

A hybrid machine learning and verification system that helps Kenyan job seekers assess whether a job posting is likely to be fraudulent, and gives government reviewers a workflow for triaging suspicious postings and recruitment entities.

Capstone project, Group 2, Data Science.

---

## 1. Problem statement

Kenyan job seekers have very few reliable, real time ways to check whether a job posting or recruitment agency is legitimate before they apply, pay a fee, hand over personal documents, or travel. Enforcement against fraudulent agencies is largely reactive: agencies are investigated, delisted, or blacklisted only after victims have already come forward. Fake overseas placements are the most severe case, because the harm can extend from financial loss to forced labour and trafficking.

The verification information that does exist is disconnected from the channels where job seekers actually encounter postings: job boards, social media, and WhatsApp groups.

## 2. What this system does

The system accepts a job posting and returns:

- a risk level,
- a verification status for the employer or recruitment agency,
- a plain language explanation of which signals drove the result,
- a recommended action for the job seeker,
- and, where appropriate, a referral into a government review queue.

It is a decision support tool. It does not make legal determinations and it does not replace any regulator's authority.

## 3. Objectives

- Build an explainable classifier that estimates the probability that a job posting is fraudulent.
- Extract scam signals from posting text, for example upfront fee requests, urgency language, vague duties, and unrealistic pay.
- Verify the named employer or agency against registry reference data, including fuzzy matching to catch near miss impersonation.
- Separate content risk from entity verification so that neither one silently overrides the other.
- Provide a government review interface with an auditable record of review decisions.
- Feed reviewed outcomes back into a versioned dataset for future retraining.

## 4. Users

**Job seekers.** Primary beneficiaries. They receive an advisory result before applying, paying, or travelling. The system informs a decision they still make themselves.

**Government reviewers.** They receive ambiguous and high risk cases, confirm or dismiss them, and build up a record of repeat entities and emerging scam patterns.

## 5. Architecture

```
                 Job seeker submits
             URL / pasted text / upload
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

Two statuses are returned, never collapsed into one:

| Risk assessment | Verification status |
| --- | --- |
| `LOW_RISK` | `VERIFIED` |
| `SUSPICIOUS` | `UNVERIFIED` |
| `HIGH_RISK` | `BLACKLISTED` |
| | `POSSIBLE_IMPERSONATION` |
| | `NOT_APPLICABLE` |

Guiding rules:

- Not found in a registry does not mean fraudulent.
- Found in a registry does not mean safe.
- Blacklisted is strong high risk evidence.
- A near miss on a registered name is a possible impersonation, not a match.

## 6. Data

Preference order: real world data first, programmatic generation only where real examples are unavailable.

| Layer | Source | Role |
| --- | --- | --- |
| Labelled fraud data | DIFrauD job scams (relabelled EMSCAD) | Trains the core text classifier |
| Real Kenyan postings | BrighterMonday, Fuzu | Local language, formats, salary norms |
| Verification reference | Mock company registry, mock agency registry | Entity lookup and blacklist checks |
| Scenario testing | Mock job postings | Pipeline, dashboard, and Kenya specific scenario tests |

Every record carries provenance so an assumed label is never mistaken for a verified one:

```
source_dataset    DIFrauD | BrighterMonday | Fuzu | MockKenyanScam | HumanReviewed
label_source      original_dataset | platform_assumed_legitimate |
                  synthetic_generation | government_review | manual_annotation
label_confidence  high | medium | low
is_synthetic      true | false
parent_record_id  set for augmented variants
```

Registry data is mock. It is clearly labelled as simulated in the interface and is not an official government source.

### Canonical posting schema

```
posting_id, title, description, company, agency, recruitment_channel,
location, country, is_overseas, salary, currency, employment_type,
email, phone, application_url, source, fraud_label
```

`fraud_label` is a column in the postings table, `0` legitimate and `1` fraudulent. Registries stay as separate lookup tables and are joined at verification time, never appended as posting rows.

## 7. Repository structure

```
job-scam-detection/
  data/
    raw/         source data, unmodified
    processed/   cleaned, schema aligned
    external/    registries and reference lookups
    synthetic/   generated records
  docs/
    architecture/    system design
    diagrams/        exported wireframes and flows
    meeting_notes/   decisions and supervisor feedback
  notebooks/     exploration and EDA
  src/
    data/            loading and cleaning
    features/        feature engineering
    models/          training and evaluation
    verification/    registry lookup and fuzzy matching
    explainability/  reason generation
  app/
    jobseeker/   job seeker interface
    government/  review dashboard
  tests/
```

Large data files are not committed. See `.gitignore`.

## 8. Working on this repo

Branch from `main`, never commit to `main` directly, open a pull request, get one review.

```
feature/readme
feature/ui
feature/data-audit
feature/data-cleaning
feature/eda
feature/modelling
```

Commit prefixes: `feat:` `fix:` `docs:` `data:` `refactor:` `test:` `chore:`

Full contribution rules are in [CONTRIBUTING.md](CONTRIBUTING.md).

## 9. Team and ownership

| Area | Owner |
| --- | --- |
| Dataset search | Whole team |
| Data loading and cleaning | Assigned |
| README and repository administration | Alex Kinyua |
| Data audit | Assigned |
| EDA | Assigned |
| Modelling | Assigned |
| UI | Alex Kinyua |
| Dashboard | Unassigned |
| Deployment | Unassigned |

Task tracking is in ClickUp. Group lead: Cleopas Karanja.

## 10. Roadmap

**Phase 1. Data.** Source real data, agree the canonical schema, audit, clean, EDA.

**Phase 2. Modelling.** TF-IDF with Logistic Regression baseline, structured feature model, comparison, imbalance handling, explainability.

**Phase 3. Verification.** Registry lookup, fuzzy matching, blacklist checks, rule based signals, decision layer.

**Phase 4. Interfaces.** Job seeker app, government dashboard, review workflow and audit trail.

**Phase 5. Integration.** End to end testing, evaluation write up, deployment, panel presentation.

## 11. Scope

**In scope.** Data pipeline, baseline and comparison models, imbalance handling, explainability, registry verification against mock data including fuzzy matching, job seeker demo app, mock review dashboard, provenance documentation.

**Stretch.** URL extraction, threshold tuning from precision and recall analysis, transformer embeddings, duplicate campaign clustering.

**Out of scope, described as future work.** Live integration with any government system, WhatsApp or USSD interfaces, live scraping of job boards, and actual adoption by government or job board partners.

## 12. Evaluation

Fraudulent postings are a small minority, so accuracy alone is not a success measure. Reported metrics are recall on the fraudulent class, precision and false positive rate, F1, PR-AUC and ROC-AUC, the confusion matrix, and a qualitative interpretability check. Real and synthetic data are evaluated separately. Test data is never augmented, and augmented variants stay in the same split as their parent record.

## 13. Disclaimer

This is a student capstone project. Registry data is simulated. Outputs are advisory only and must not be treated as an official verification of any company, agency, or job posting.
