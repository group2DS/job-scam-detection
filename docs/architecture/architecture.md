# System Architecture

Version 0.1, drafted 27 August 2026. This document is the reference for how components fit together. Changes here should be raised with the group before implementation.

---

## 1. Design principle

No single model decides the outcome. Content risk, entity verification, and human judgement are separate concerns that are combined at the end, and each one is reported to the user.

This matters because the two failure modes are not symmetric. A missed scam can cost someone their savings or their safety. A false alarm costs a legitimate employer an applicant. The system is tuned to catch fraud, and it manages false alarms by explaining itself rather than by hiding uncertainty behind a single number.

## 2. Entry points

| Entry point | Who uses it | Behaviour |
| --- | --- | --- |
| Pasted text | Job seeker | Primary path, always available |
| URL | Job seeker | Attempts structured extraction, falls back to asking for pasted text |
| Uploaded file or screenshot | Job seeker | Stretch goal, needs OCR |
| Pre publication screening | Job board or agency | Future work, same engine |

Extraction failure is never treated as evidence of fraud.

## 3. Pipeline

### Step 1. Content extraction

Normalise the submission into a posting object:

```
title, description, employer_name, agency_name, recruitment_channel,
location, destination_country, salary, currency, contact_email,
contact_phone, application_url, fees_mentioned, contract_information
```

Missing fields are recorded as missing, not imputed silently. Completeness is itself a signal.

### Step 2. Recruitment context

Determine before any lookup:

- local or overseas,
- direct employer or recruitment agency,
- named entity present or absent.

This decides which registry applies. A direct employer advertising its own vacancy is not a recruitment agency and must not be penalised for being absent from an agency register.

### Step 3. NLP classifier

Produces a content risk probability from the posting text.

Excluded from the training features, because they leak the target or belong to a later stage:

```
fraud_label, red_flags, registry_match_status, blacklist result
```

### Step 4. Rule based signals

Deterministic, explainable checks that produce structured evidence rather than an opaque score:

- upfront fee requested, including placement, visa, medical, training, or flight fees
- payment requested to a personal mobile money number
- passport retention mentioned
- contract only after arrival
- extreme urgency or artificial scarcity
- no interview or no CV required
- salary far outside the normal range for the role and market
- personal email domain while claiming to be a large organisation
- shortened or mismatched application link
- claimed government affiliation

### Step 5. Entity verification

Look the named entity up in the applicable registry and return:

```
entity_type       company | agency | unknown
registry_status   verified | not_found | blacklisted | shell | expired
match_score       0.0 to 1.0
match_type        exact | fuzzy | none
blacklist_match   true | false
```

Fuzzy matching catches near miss impersonation of real registered names. A high similarity score with no exact match is `POSSIBLE_IMPERSONATION`, which is a warning, not a pass.

### Step 6. Decision layer

Combines the content risk probability, rule signals, verification result, blacklist evidence, recruitment context, and completeness into:

- a risk level,
- a verification status,
- a ranked list of reasons,
- a recommended action,
- a routing decision.

Initially rule based and transparent rather than a second model, so it can be explained and defended.

### Step 7. Output

Two independent statuses, never collapsed into one.

**Risk assessment:** `LOW_RISK`, `SUSPICIOUS`, `HIGH_RISK`

**Verification status:** `VERIFIED`, `UNVERIFIED`, `BLACKLISTED`, `POSSIBLE_IMPERSONATION`, `NOT_APPLICABLE`

| Risk | Verification | Message to the job seeker |
| --- | --- | --- |
| Low | Verified | No strong scam indicators, entity found. Stay cautious. |
| Low | Unverified | No strong scam indicators, but the entity could not be verified. |
| Suspicious | Verified | Registered entity, but the posting content raises concerns. |
| Suspicious | Possible impersonation | The name closely resembles a registered organisation without matching it. |
| High | Blacklisted | Strong warning. Do not pay or send documents. Referred for review. |
| High | Unverified | Strong scam indicators and no verified entity. |

The word "safe" is not used. The system reports lower risk, never guaranteed safety.

## 4. Government flow

Cases are routed for review when:

- content is scored suspicious or high risk,
- the entity cannot be verified,
- a name is a near miss against a registered entity,
- a posting claims a government programme or government linked placement,
- an overseas posting has incomplete agency, employer, contract, or destination detail,
- components disagree, for example clean text with a blacklisted entity.

A reviewer resolves a case as confirmed legitimate, confirmed scam, needs more evidence, duplicate, or entity verified but posting still suspicious.

Every case records the model probability, the rule flags, the verification result, the system tier, the reviewer decision, the stated reason, and the timestamp.

Reviewed outcomes enter a versioned retraining pool. They are not fed back into the model automatically. A reviewer clicking a button is not a training event.

## 5. Data model

Five tables, deliberately separate:

| Table | Grain |
| --- | --- |
| `job_postings_master` | one row per posting, carries `fraud_label` |
| `company_registry` | one row per company |
| `agency_registry` | one row per recruitment agency |
| `blacklist` | one row per blacklisted entity, email, domain, or phone number |
| `review_cases` | one row per government review decision |

Registries are joined at verification time. They are never appended to the postings table as if a company were a job posting.

## 6. Known limitations

- Registry data is simulated. Absence from it proves nothing about the real world.
- Synthetic postings generated from separate legitimate and fraudulent templates can produce unrealistically clean class separation. They are used mainly for pipeline and scenario testing.
- Postings collected from job boards are real postings, not verified legitimate postings, and are labelled with medium confidence.
- The system does not detect scams that use flawless language and a verified stolen identity.
- Outputs are advisory. No legal conclusion is asserted about any named entity.
