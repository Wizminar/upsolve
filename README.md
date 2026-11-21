# Upsolve: a Codeforces practice coach

CS698B course project by **The Syndicate**: Ashirvad Dwivedi, Mohit Shankar Pawar, Chaitanya Kumar, Bishal Podder.

Enter a public Codeforces handle. Upsolve imports the submission history, rates you per topic,
and recommends problems with an estimated **50–70% solve probability**, each with a written reason.
It has three connected views (Today, Insights, Week plan) and a plugin system for the cross-dev team.

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000
```

Open http://localhost:8000. API docs are at http://localhost:8000/api/docs.

The repository ships with `data/dataset_handles.csv` and a trained `data/model.json`. To rebuild them:

```bash
.venv/bin/python -m scripts.build_dataset --from-csv   # re-import the documented handles (~25 min, rate limited)
.venv/bin/python -m scripts.train_model                # fit + evaluate, writes data/model.json
.venv/bin/python -m scripts.export_openapi             # writes docs/openapi.json
.venv/bin/python -m pytest -q                          # 26 tests, no network needed
```

**Demo tip:** sync the demo handles before the demo, because Codeforces limits clients to one request per 2 s.
Problem metadata is cached for 24 h, and later syncs only fetch new submissions.

## How the five components map to the code

| Component | Where | What it does |
|---|---|---|
| **ETL** | `app/cf_client.py`, `app/etl.py`, `app/db.py` | Pulls profiles, submissions, contest rating history and problem metadata from the Codeforces API (paced at ≤1 request / 2.1 s, with retries). It drops gym problems and the `*special` tag, deduplicates submissions by id and reused Div1/Div2 statements by name+rating, then groups submissions into **attempts**: one per problem, starting at the first *eligible* submission (compilation errors and pending verdicts ignored), and **solved if accepted within 24 h**. Sync is incremental (stops at the last stored id, re-checks pending verdicts). Everything is stored in SQLite (`data/upsolve.db`). |
| **AIML** | `app/elo.py`, `app/model.py`, `app/coach.py` | (1) An **anchored Elo** model: the overall rating is the contest rating at the time of each attempt plus a decaying "practice form" offset, and every topic has its own offset, re-centred so topic ratings show relative strength. Attempt data is biased (people mostly submit to problems they expect to solve), so every rated contest a user entered also adds **implicit failures**: each problem of that round they never attempted counts as an unsolved game. (2) A **logistic-regression** classifier over 11 features computed *before* each attempt (Elo log-odds, gaps to overall and to the weakest tag, tag evidence and solve rates, recent form, recency, difficulty, contest flag). It is trained on 200 public histories stratified by rating, evaluated with a **chronological 80/20 split**, and reported with AUC, log loss, Brier score and calibration bins against the Elo baseline. Estimates are made in "seen it" mode (the contest context), which is the conservative choice. If `model.json` is missing, Elo estimates are used. (3) A recommender that scores unsolved problems by closeness to 60%, training focus, weak topics, upsolve opportunities and recency, with topic and contest diversity. A recommendation log records each estimate so later syncs can check it. |
| **VIZ** | `static/js/charts.js`, `static/js/views/*` | The rating ladder with today's problems pinned on it, topic-strength bars with evidence counts and hatching for low evidence, topic-rating trends, contest-rating history on rank bands, an activity heatmap, and a calibration plot. |
| **APP** | `app/main.py`, `static/` | FastAPI serves plain HTML/CSS/JS with no build step and no login. Users sync a handle, inspect insights, get recommendations, and choose up to two training topics with a weekly target. The week plan and tally update from accepted submissions after each sync. A script-free summary is at `/text/<handle>`. |
| **DEV** | `app/main.py`, `app/plugins.py`, `static/js/plugin-host.js`, `docs/PLUGINS.md` | Versioned REST API (`/api/v1`) with an OpenAPI 3 document (`docs/openapi.json`), configurable CORS (`UPSOLVE_CORS_ORIGINS`), and an **in-app plugin system**. Plugins in `plugins/<id>/` get a tab or a panel inside Upsolve, the API client, events, and a per-plugin JSON store (`/api/v1/plugins/{id}/store/...`). Example: `plugins/rival`. |

### Accessibility features

- WCAG AA contrast for text, with darker text variants of the rank colours.
- Colour is never the only signal: each rank colour sits next to its rating number or name, low evidence is hatched, the overall rating is a dashed line, and solved/unsolved use ✓/✗.
- Every chart has `role="img"` with a text summary, a legend, and a "Show data as a table" toggle.
- Full keyboard use: skip link, arrow keys in the tablist and the topic list, and a visible focus ring.
- Screen-reader support: live regions for sync progress and status messages, plus semantic headings, lists and tables.
- Respects `prefers-reduced-motion` and `prefers-color-scheme` (dark theme), and works at phone width.
- Uses Atkinson Hyperlegible Next for body text, a typeface designed for low-vision readers.
- Script-free text view at `/text/<handle>` for text browsers such as lynx.

## API at a glance

| Method | Path | Purpose |
|---|---|---|
| POST / GET | `/api/v1/users/{handle}/sync` | Start an import / poll its status |
| GET | `/api/v1/users` | Synced handles |
| GET | `/api/v1/users/{handle}/profile` | Ratings, counts, model source |
| GET | `/api/v1/users/{handle}/topics` | Topic ratings with evidence |
| GET | `/api/v1/users/{handle}/topics/{tag}/history` | Daily topic rating trend (`__overall__` for overall) |
| GET | `/api/v1/users/{handle}/rating-history` | Official contest rating |
| GET | `/api/v1/users/{handle}/activity` | Submissions per day |
| GET | `/api/v1/users/{handle}/attempts` | Grouped attempts |
| GET | `/api/v1/users/{handle}/recommendations` | Daily problems with reasons |
| GET | `/api/v1/users/{handle}/predict/{problem_id}` | Probability + per-feature contributions |
| GET | `/api/v1/users/{handle}/feedback` | How past recommendations turned out |
| GET / PUT | `/api/v1/users/{handle}/training` | Focus topics (≤2) and weekly target |
| GET | `/api/v1/users/{handle}/plan` | This week's plan and progress |
| GET | `/api/v1/topics`, `/api/v1/problems`, `/api/v1/model`, `/api/v1/health` | Catalog and model report |
| GET / PUT | `/api/v1/plugins`, `/api/v1/plugins/{id}` | Plugin registry, enable/disable |
| GET / PUT / DELETE | `/api/v1/plugins/{id}/store/{scope}/{key}` | Plugin data store |

## Third-party code, data and services

| What | Used for | Licence |
|---|---|---|
| [Codeforces API](https://codeforces.com/apiHelp) | All problem, submission and rating data (public endpoints, no key) | Codeforces terms of use |
| FastAPI, Starlette, Pydantic, Uvicorn | Web framework, validation, server | MIT / BSD |
| httpx | HTTP client for the Codeforces API | BSD |
| NumPy | Inference and metrics | BSD |
| scikit-learn | Fitting the logistic regression (training only) | BSD |
| pytest | Tests | MIT |
| SQLite (Python stdlib) | Storage | Public domain |
| Google Fonts: Schibsted Grotesk, Atkinson Hyperlegible Next | Typefaces | SIL Open Font License |

The charts, plugin host, ETL rules, Elo variant, features and recommender are our own code
(written with AI assistance, see the report). The rank colour scheme follows Codeforces conventions.

## Report checklist (for the final PDF)

- [ ] Five components (table above), with screenshots of each view.
- [ ] API: include `docs/openapi.json` (or the Swagger UI pages) and the table above.
- [ ] Testing: `pytest -q` output; the tests cover the attempt rules, incremental sync, Elo properties, leakage-free replay, metrics, the training artifact, every endpoint, and the plugin store.
- [ ] Model evaluation: paste the output of `scripts/train_model.py` and the calibration plot.
- [ ] Dataset: describe `data/dataset_handles.csv` (stratified by 200-point rating buckets from recent rated rounds).
- [ ] Third-party disclosure (table above).
- [ ] **AI usage section, written by the team members themselves** (required by the course; it must not be AI-written).
- [ ] Cross-dev portion: the plugin you built for the partner team's system.
