# Contributing

Read this before your first commit. It exists so that six people can work in
parallel without overwriting each other or breaking `main`.

---

## 1. One time setup

```bash
git clone git@github.com:group2DS/job-scam-detection.git
cd job-scam-detection

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

git config user.name "Your Name"
git config user.email "your.email@student.example"
```

Check it works:

```bash
python -m pytest tests/ -q
```

## 2. Golden rules

1. Never commit directly to `main`.
2. Never commit large data files. Raw and processed data are gitignored.
3. Never commit credentials, API keys, or `.env` files.
4. One branch per task. One pull request per branch.
5. Pull before you start, and before you push.
6. Every file goes in its designated folder. Nothing lands in the repository
   root unless it is a root level config file.

## 3. Where files go

The root directory is for project level files only: `README.md`,
`CONTRIBUTING.md`, `requirements.txt`, `pytest.ini`, `.gitignore`.

Everything else has a home:

| What you are adding | Where it goes |
| --- | --- |
| Jupyter notebook | `notebooks/` |
| Cleaning or feature code | `src/data/`, `src/features/` |
| Model training code | `src/models/` |
| API route | `src/api/routes/` |
| Test | `tests/` |
| Reference data, registries | `data/external/` |
| Documentation | `docs/` |
| Meeting notes, supervisor feedback | `docs/meeting_notes/` |
| Diagrams, wireframes, screenshots | `docs/diagrams/` |
| Frontend code | `app/jobseeker/` or `app/government/` |

If you are unsure, ask before pushing. Moving a file later rewrites its
history and breaks anyone who already pulled it.

### Notebook naming

```
notebooks/NN_topic.ipynb
```

For example `01_data_audit.ipynb`, `02_eda.ipynb`, `03_modelling.ipynb`. The
number fixes the reading order, so a new person can follow the work without
asking which notebook came first.

## 4. Branch naming

```
<type>/<short-description>-<yourname>
```

| Type | Use for |
| --- | --- |
| `feature` | new capability |
| `fix` | bug fix |
| `docs` | documentation only |
| `data` | dataset or schema changes |
| `chore` | tooling, config, housekeeping |

Examples:

```
feature/government-dashboard-briannah
fix/url-ingestion-alex
docs/architecture-christopher
data/schema-mapping-melisa
```

Lowercase, hyphen separated, no spaces. The name goes last so branches still
group by type when sorted. Including your name means anyone, including an
instructor reviewing the repository, can trace who did what without opening
every commit.

## 5. Daily workflow

```bash
git checkout main
git pull origin main

git checkout -b feature/your-task-yourname
git branch --show-current          # confirm the switch actually happened

# do the work

git add <specific files>
git status --short                 # check nothing unexpected is staged
git commit -m "feat: short description"
git push -u origin feature/your-task-yourname
```

Then open a pull request into `main`, request one reviewer, and update your
ClickUp task once it is merged.

**Always run `git branch --show-current` before committing.** If `checkout -b`
fails because the branch already exists, it prints a warning that is easy to
miss, and your work lands on `main`.

Stage specific files rather than `git add .` where you can. It keeps
accidental files out of the history.

## 6. Commit messages

```
<type>: <what changed, imperative, lowercase>
```

Same types as branches, plus `refactor:` and `test:`.

Good:

```
feat: add tf-idf baseline classifier
fix: reject non-listing pages during url ingestion
docs: document canonical posting schema
data: add brightermonday schema mapping
```

Avoid `update`, `changes`, `final`, `final2`, `work`.

Commit in meaningful units. Several small commits beat one commit at midnight
containing everything.

## 7. Pull requests

Title: same style as a commit message.

Body should cover three things:

```
What this changes and why

How to verify it

Anything the reviewer should watch for
```

One approval required before merge. If you are reviewing, actually open the
files. If something is unclear, ask in the PR rather than in WhatsApp, so the
reasoning stays with the code.

Delete your branch after merging. GitHub offers a button for this.

## 8. Tests

Any change to `src/` must leave the test suite passing:

```bash
python -m pytest tests/ -q
```

If you add a capability, add a test for it. If a test fails and you believe
the test is wrong, say so in the PR rather than deleting it.

## 9. Notebooks

- Restart and run all before committing, so the outputs match the code.
- Notebooks are for exploration. Anything reused belongs in `src/`.
- Use relative paths. Do not read from an absolute path on your own machine.
- Do not commit a notebook containing an API key or a password.

## 10. Data rules

- `data/raw/` is read only. Never edit a raw file in place.
- Cleaning writes to `data/processed/`.
- Registries and lookups live in `data/external/`.
- Generated records live in `data/synthetic/`.
- Every dataset needs a short note in `docs/` recording where it came from,
  when it was collected, how it is licensed, and whether the labels are
  verified, assumed, or generated.
- Real world data is preferred. Generate records only where real examples are
  unavailable, and mark them `is_synthetic`.

Because data files are gitignored, share them through the group drive and keep
the file names identical across machines.

### Splitting rule

Split on the `fingerprint` column, not the row index. The source data contains
near duplicate postings, and a random split scatters copies of the same advert
across train and test. The model then sees the answer at test time and scores
well for the wrong reason.

## 11. Schema discipline

The canonical posting schema is defined in the README. If you need to add,
rename, or drop a field, raise it with the group before changing your own copy.
Silent schema drift is the fastest way to break everyone else's notebooks.

The same applies to `src/core/schemas.py`. The status enums are a closed set
that both interfaces render directly. Adding a member means updating the
frontend mapping in `app/jobseeker/src/lib/display.js` as well.

## 12. Documentation

If a decision is made in a meeting or by a supervisor, it goes into
`docs/meeting_notes/` the same day, with the date and the reasoning. Exported
diagrams and wireframes go into `docs/diagrams/`.

## 13. If something breaks

```bash
git status                  # what state am I in
git log --oneline -10       # recent history
git reflog                  # every commit, including ones you reset away
git restore <file>          # discard uncommitted changes to a file
git restore --staged <file> # unstage without losing changes
```

`git reflog` is the one worth remembering. A commit you lost to a bad reset is
almost always still there.

Do not force push to `main`. If you are stuck, stop and ask in the group before
running anything destructive.
