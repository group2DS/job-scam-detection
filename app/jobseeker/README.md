# Job Seeker Interface

Public facing interface. A person pastes a job listing and gets back a risk
assessment, a verification status, the reasons behind both, and a
recommendation.

---

## Run it

The API must be running first, in a separate terminal from the repo root:

```bash
python -m uvicorn src.api.main:app --reload
```

Then:

```bash
cd app/jobseeker
npm install
npm run dev
```

Opens on `http://localhost:5173`. The API's CORS settings already allow that
origin.

To point at a deployed API, copy `.env.example` to `.env` and set
`VITE_API_URL`.

## Structure

```
src/
  main.jsx              entry point
  App.jsx               page state: idle, loading, error, result
  components/
    SubmitForm.jsx      URL and paste input
    Result.jsx          the two statuses, reasons, recommendation
  lib/
    api.js              the only file that knows the backend exists
    display.js          enum to label, tone and copy mapping
  styles/
    app.css             tokens and layout
```

`lib/display.js` is the file to edit when wording or colour changes. Nothing
else hard codes a status label.

## Design rules

**Two statuses, never merged.** Risk and verification are rendered as separate
blocks. The case that matters is a listing that reads cleanly but whose
employer cannot be confirmed, and a single combined verdict cannot express
that honestly.

**The word "safe" is never used.** The lowest tier reads "Lower risk". The
system cannot guarantee safety and the copy must not imply it can.

**Unverified is not an accusation.** The copy says the organisation could not
be found and that this is not proof of fraud. Many legitimate small employers
are absent from an incomplete registry.

**Reasons are always shown.** A bare score tells a job seeker nothing they can
act on. Naming the fee request lets them recognise the same pattern elsewhere,
even without the tool.

**Paste is the primary path.** Scam listings circulate on social media and
messaging apps where there is often no clean URL, so the paste tab is the
default and a failed URL fetch is treated as a usability problem rather than a
fraud signal.

**Mobile first.** The base stylesheet targets a phone; the two column layout is
a progressive enhancement above 620px.

## Development mode

When the API runs without trained model artefacts, the response carries a
`model_version` beginning with `stub` and the UI displays a notice saying so.
This is deliberate. A placeholder result must never be mistaken for a trained
model's output during a demonstration.

## Adding a status

If the API gains a new `risk_level` or `verification_status` member, add it to
`lib/display.js` with a label, a tone and a one line summary. Unmapped values
fall back to a neutral badge rather than breaking the page, but they will read
as "Unknown" until mapped.
