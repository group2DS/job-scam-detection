# SafeHire Government Dashboard Backend Contract

## Verification information

- Branch: feature/dashboard
- Commit:
- Local API: http://127.0.0.1:8000
- Production API: configured separately
- Verification date:

## Authentication

- Method:
- Path:
- Content type:
- Request body fields:
- Success status:
- Token field:
- Token type:
- Reviewer field:
- Invalid-credentials status:
- Rate-limit response:

## Case queue

### GET /api/cases

- Requires authentication:
- Query parameters:
- Search parameter:
- Pagination parameters:
- Risk filter:
- Verification filter:
- Workflow-status filter:
- Market filter:
- Collection field:
- Total-count field:
- Current-page field:
- Empty response:

## Case statistics

### GET /api/cases/stats

- Requires authentication:
- Response fields:
- Meaning and scope of each field:

## Case detail

### GET /api/cases/{id}

- Case-ID type:
- Posting fields:
- Risk-level field:
- Verification-status field:
- Model-probability field:
- Reasons field:
- Workflow-state field:
- Audit-trail field:
- Not-found response:

## Reviewer decision

### POST /api/cases/{id}/decision

- Requires authentication:
- Request body:
- Allowed values:
- Required fields:
- Optional fields:
- Success status:
- Invalid-transition status:
- Finalized-case behavior:

## Confirmed workflow transitions

- pending:
- under_review:
- confirmed_scam:
- confirmed_legit:
