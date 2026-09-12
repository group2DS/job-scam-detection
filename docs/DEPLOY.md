# Deployment

Three pieces: a Postgres database, the API, and the job seeker interface.
All on free tiers.

| Piece | Host | Why |
| --- | --- | --- |
| Database | Render Postgres | Render's disk is ephemeral, so SQLite would lose every case on restart |
| API | Render | Runs the Python service, wires the database automatically |
| Frontend | Vercel | Static build, fast, free |

Budget about 40 minutes for the first run.

---

## Before you start

### 1. Apply the config change

`src/core/config.py` needs replacing. Two things it adds:

- Rewrites the `postgres://` scheme Render hands out into `postgresql://`,
  which SQLAlchemy 2.0 requires. Without this the API will not start.
- Reads `CORS_ORIGINS` as a comma separated string instead of JSON, so the
  value pasted into the Render dashboard works as typed.

Then one line in `src/api/main.py`:

```python
    allow_origins=settings.cors_origin_list,
```

It currently reads `settings.cors_origins`.

Verify:

```bash
python -m pytest tests/ -q
python -m uvicorn src.api.main:app --reload
```

The deprecation warning about class-based config should also be gone, since
the replacement uses `SettingsConfigDict`.

### 2. Decide about the model

`artifacts/` is gitignored, so the deployed API will run the **stub
classifier** unless the trained files are committed. `/api/health` would
report `"model": "stub"` in front of the panel.

To ship the real model, add to `.gitignore`:

```gitignore
# Trained model artefacts are deliberately versioned for deployment
!artifacts/model.pkl
!artifacts/vectorizer.pkl
```

Then:

```bash
git add -f artifacts/model.pkl artifacts/vectorizer.pkl
```

Check the size first with `ls -lh artifacts/`. Anything under about 50 MB is
fine for git. A TF-IDF vectoriser with 50,000 features plus a logistic
regression should be comfortably under that.

If Cleopas has not exported yet, deploy on the stub now and redeploy when the
artefacts land. Do not wait: a working deployed stub beats an undeployed
trained model on Wednesday.

### 3. Commit the blueprint

Copy `render.yaml` to the repository root and push.

---

## Database and API

1. Go to **dashboard.render.com**, sign in with GitHub.
2. **New** → **Blueprint**.
3. Select the `job-scam-detection` repository. Render reads `render.yaml`.
4. It will show one web service and one database. **Apply**.
5. Wait for the build. First one takes five to ten minutes.

The `DATABASE_URL` is wired automatically by the blueprint. You do not need to
copy it.

When it finishes you will have a URL like
`https://job-scam-api.onrender.com`. Check it:

```bash
curl https://job-scam-api.onrender.com/api/health
```

Expect `{"status":"ok", ..., "model":"stub"}` or `"trained"`.

Then confirm the pipeline works in production:

```bash
curl -X POST https://job-scam-api.onrender.com/api/analyse \
  -H "Content-Type: application/json" \
  -d '{"text":"Title: Hotel Staff\nAgency: Swift Resources Agency\nLocation: Qatar\nPay a registration fee of KES 5000 via Mpesa to secure the position. Applicants should have experience in hotel service."}'
```

High risk, blacklisted, with a case ID means the registries loaded and the
database is writing.

---

## Frontend

1. Go to **vercel.com**, sign in with GitHub.
2. **Add New** → **Project**, import the repository.
3. Set **Root Directory** to `app/jobseeker`. This is the step people miss.
4. Framework preset should detect **Vite**. Leave build settings alone.
5. Add an environment variable:

```
VITE_API_URL = https://job-scam-api.onrender.com
```

No trailing slash.

6. **Deploy**.

You will get a URL like `https://job-scam-detection.vercel.app`.

---

## Close the loop

The API does not yet allow the Vercel domain, so the frontend will fail with a
CORS error until you tell it.

In Render, open the service, **Environment**, set:

```
CORS_ORIGINS = https://job-scam-detection.vercel.app,http://localhost:5173
```

Use your actual Vercel URL. Keeping localhost in the list means local
development still works.

Save. Render redeploys automatically. Then open the Vercel URL and submit a
listing end to end.

---

## Two things that will bite you

### Cold starts

Render's free tier spins a service down after 15 minutes of inactivity. The
next request takes **50 seconds or more** while it wakes.

In a live demo that is a disaster. Open the API URL five minutes before you
present and leave a tab on it. If you want insurance, a free uptime monitor
pinging `/api/health` every 10 minutes keeps it warm.

Say this out loud if it happens: free tier cold start, not a system fault.

### The database expires

Render's free Postgres is deleted after 30 days. Fine for a capstone, worth
knowing before anyone assumes the deployment is permanent.

---

## After it is live

Update the README with both URLs, and add a line to the disclaimer that the
deployment is a demonstration.

Briannah will need `CORS_ORIGINS` extended with the dashboard's domain once
that deploys, and her frontend pointed at the same API URL. That is the
moment the two interfaces start sharing real cases.

---

## Troubleshooting

**Build fails on `psycopg2-binary`.** Check `PYTHON_VERSION` is `3.12.3` in
the Render environment. The blueprint sets it.

**API starts then crashes.** Read the logs. A `Can't load plugin
sqlalchemy.dialects:postgres` error means the config change was not applied.

**CORS error in the browser console.** The Vercel URL is missing from
`CORS_ORIGINS`, or has a trailing slash. It must match the origin exactly.

**Frontend builds but shows a network error.** `VITE_API_URL` is wrong or was
added after the build. Vite inlines environment variables at build time, so
redeploy after changing it.

**Registries empty, everything returns unverified.** The CSVs in
`data/external/` were not committed. Check with
`git ls-files data/external/`.
