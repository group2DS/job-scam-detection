# API Service

FastAPI backend serving both interfaces. The job seeker app and the
government dashboard talk to this and nothing else.

---

## Run it

```bash
pip install -r requirements.txt
uvicorn src.api.main:app --reload
```

Interactive docs at `http://localhost:8000/docs`.

It starts without a trained model. When `artifacts/model.pkl` is absent a
keyword stub supplies the probability so the pipeline runs end to end.
`/api/health` reports which is active, and the log warns on startup. Frontend
work is never blocked on modelling.

```bash
pytest tests/ -v      # 23 tests, no services required
```

## The central design commitment

Content risk and entity verification are computed independently and reported
independently. Neither silently overrides the other.

```
not found      is not the same as fraudulent
found          is not the same as safe
blacklisted    is strong evidence of harm
near match     is possible impersonation, never a pass
```

This is why `RiskLevel` and `VerificationStatus` are separate enums, why the
classifier never receives registry data, and why the decision layer is
readable rule based code rather than a second model.

## Structure

```
src/
  core/schemas.py          shared contracts, every stage speaks these
  core/config.py           settings and thresholds
  ingestion/extractor.py   raw input -> Posting
  models/classifier.py     text -> probability, with stub fallback
  rules/engine.py          deterministic scam signals
  verification/registry.py registry lookup, fuzzy match, blacklist
  decision/layer.py        fuses everything, assigns tier, routes
  db/models.py             review cases and audit entries
  api/routes/analyse.py    POST /api/analyse
  api/routes/cases.py      government review endpoints
```

Each stage has one job and is independently testable. Swapping the stub for
CK's trained model touches `classifier.py` only.

## Request flow

```
POST /api/analyse {url | text}
  1. extractor.from_text() or from_url()  -> Posting
  2. classifier.predict()                 -> probability
  3. engine.evaluate()                    -> rule hits
  4. registry.verify()                    -> verification status
  5. layer.combine()                      -> tier, reasons, routing
  6. if referred: write ReviewCase + AuditEntry
```

Referral is just a database write. The dashboard reads the same table through
`GET /api/cases`. No message queue, no integration layer, nothing that can
fail during a demonstration.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/analyse` | Assess a posting |
| GET | `/api/cases` | Review queue, filterable |
| GET | `/api/cases/stats` | Dashboard summary tiles |
| GET | `/api/cases/{id}` | Case detail with audit trail |
| POST | `/api/cases/{id}/decision` | Record a reviewer decision |
| GET | `/api/health` | Status, including stub or trained |

## Example

```bash
curl -X POST http://localhost:8000/api/analyse \
  -H "Content-Type: application/json" \
  -d '{"text":"Title: Hotel Staff\nAgency: Bright Future Recruitmnt Agancy\nPositions in Qatar."}'
```

```json
{
  "risk_level": "suspicious",
  "verification_status": "possible_impersonation",
  "probability": 0.15,
  "reasons": [
    {
      "code": "possible_impersonation",
      "text": "The name 'Bright Future Recruitmnt Agancy' closely resembles 'Bright Future Recruitment Agency' without matching it, which can indicate impersonation of a registered organisation.",
      "source": "registry"
    }
  ],
  "referred_for_review": true,
  "case_id": "C-3F9A21"
}
```

## Verified behaviour

Five scenarios, all covered by tests:

| Input | Risk | Verification | Referred |
| --- | --- | --- | --- |
| Safaricom PLC, clean text | Lower risk | Verified | No |
| Unknown employer, clean text | Suspicious | Unverified | Yes |
| Misspelled agency name | Suspicious | Possible impersonation | Yes |
| Blacklisted agency | High risk | Blacklisted | Yes |
| Fee scam under a real company name | High risk | **Verified** | Yes |

The last row is the important one. The entity verifies, and the posting is
still high risk, because a registered organisation's name can be attached to
a fraudulent advertisement. A system that let verification clear a posting
would miss it.

The second row is the most common real outcome and the reason the two status
design exists: nothing in the text is alarming, but the employer could not be
confirmed, so the user is cautioned rather than accused.

## Configuration

Thresholds live in `config.py` and are tunable without retraining:

```
high_risk_threshold      0.70
suspicious_threshold     0.35
impersonation_threshold  0.75
```

Set `DATABASE_URL` to a Postgres URL in deployment. SQLite is the local
default so the project runs with no services installed.

## Registry data

CSVs in `data/external/`, read at startup rather than stored in the database
so reference data can be updated without a migration.

All entries are simulated and flagged `record_is_mock`. Absence from these
files proves nothing about the real world, and the interface says so.

## Notes for the frontend

`risk_level` and `verification_status` are closed sets. Render exactly those
values and nothing else. Do not merge them into a single badge, and do not
use the word "safe" anywhere. The system reports lower risk, never guaranteed
safety.

Always render the `reasons` array. A bare score tells a job seeker nothing
they can act on; naming the fee request lets them recognise the pattern
again elsewhere.
