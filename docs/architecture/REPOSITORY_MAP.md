# Repository Map

Where everything lives in the Repechage repository, and the conventions that
hold the layout together.

## Tree

```
razor_recover/
|-- README.md                     product overview + benchmark results
|-- CHANGELOG.md                  versioned release history
|-- LEARNING_LOG.md               every incident, root cause, and fix
|-- DEPLOY.md                     Render deployment walkthrough
|-- render.yaml                   Render blueprint (free tier, env placeholders)
|-- LICENSE                       MIT
|-- .env.example                  placeholder environment template
|
|-- backend/
|   |-- main.py                   FastAPI app: pages, webhooks, summary,
|   |                             escalation routes wiring
|   |-- auth.py                   Google OAuth + JWT session cookies
|   |-- dashboard_actions.py      escalation Approve/Dismiss routes
|   |-- config.py                 environment config + Razorpay client
|   |-- db.py                     SQLAlchemy engine (hardened pool) + Base
|   |-- models.py                 8 ORM models
|   |-- execution_config.py       execution-policy constants (env-overridable)
|   |-- EXECUTION_POLICY.md       normative execution rules
|   |-- GROUND_TRUTH_POLICY.md    normative benchmark rules
|   |
|   |-- generate_synthetic_data.py  seeded dataset + ground truth
|   |-- detect_at_risk.py           baseline detector (observed signals only)
|   |-- evaluate.py                 detector evaluation report
|   |-- run_agent.py                recovery agent runner (gates, retries)
|   |-- llm_provider.py             OpenRouter structured-decision client
|   |-- simulate_outcomes.py        fixed simulation economics + reports
|   |-- execute_recovery.py         policy-gated live execution
|   |-- agent_recommendations.py    read-only agent reasoning pass
|   |-- demo_scenarios.py           6 execution-demo Test Mode orders
|   |-- demo_scenarios_extra.py     3 escalation-practice orders
|   |-- alembic/                    migrations 001-006
|   |-- requirements.txt            pinned runtime dependencies
|
|-- frontend/
|   |-- index.html                 public landing page
|   |-- login.html                 Google sign-in
|   |-- dashboard.html             authenticated overview
|   |-- analytics.html             benchmark + agent evaluation charts
|   |-- audit.html                 filterable audit trail
|   |-- developers.html            API reference
|   |-- resources.html             policies, reports, repo links
|   |-- security.html              trust model
|   |-- theme.css                  shared design system (tokens + primitives)
|   |-- js/                        ES modules (no framework, no bundler)
|       |-- api.js                 fetch layer (auth, summary, escalations)
|       |-- state.js               per-load shared state
|       |-- utils.js               escaping, formatting, audit helpers
|       |-- charts.js              hand-rolled SVG chart primitives
|       |-- navigation.js          shared top navigation
|       |-- dashboard.js / analytics.js / audit.js   page modules
|
|-- tests/
|   |-- run_all.sh                 single entry point for all suites
|
|-- reports/                       evaluation reports (.txt raw + .md readable)
|   |-- baseline.md / baseline.txt                  detector evaluation
|   |-- baseline_simulation.md / baseline_simulation.txt   benchmark simulation
|   |-- agent_performance_result.md / agent_performance_result.txt   Gate B result
|   |-- nemotron_15_event_sample.md / nemotron_15_event_sample.txt   pinned-model sample
|
|-- evaluation/
|   |-- METRICS.md                 consolidated metrics with provenance labels
|   |-- FAILURE_ANALYSIS.md        per-layer failure record
|   |-- data/                      CSV snapshots of the benchmark tables
|
|-- pitch/                         pitch and demo deck PDFs
|   |-- test_phase0.py             live-API smoke tests (server required)
|   |-- test_run_agent_durability.py  mock-based persistence tests
|   |-- dashboard_summary_check.py    summary vs source reports
|   |-- gate_b_dry_run_5.md        5-event dry run record
|   |-- failure_demo_framing.md    stopping-rule demo framing
|
|-- docs/
|   |-- architecture/              application architecture, database
|   |                              architecture, repository map
|   |-- engineering-decisions/     why the stack and approaches were chosen
|   |-- specifications/            project specifications
|   |-- workflow/                  application workflow
|   |-- build-plan/                build plan + phase plans (0-4)
|   |-- design/                    UI V2 design documentation
|
|-- evaluation/                    pinned-model run outputs
```

## Conventions

- **Backend modules map 1:1 to pipeline stages.** File name = responsibility;
  no module does two stages.
- **Frontend has no framework.** Static HTML + ES modules served by FastAPI;
  same origin keeps the httpOnly session cookie working without CORS.
- **Reports are dual-format.** `.txt` = raw script output (provenance),
  `.md` = readable transcription. Numbers are identical.
- **Docs are emoji-free** and use plain text labels (Implemented /
  Partially implemented / Planned) instead of status symbols.
- **Historical documents are never edited.** Chat summaries, handoffs, and
  day plans describe the state at the time they were written; corrections
  happen in new documents or the learning log.

## Where to look first

| Question | Go to |
|---|---|
| How does the pipeline work? | `docs/workflow/WORKFLOW.md` |
| What do the tables look like? | `docs/architecture/DATABASE.md` |
| What are the policy rules? | `backend/EXECUTION_POLICY.md`, `backend/GROUND_TRUTH_POLICY.md` |
| Why these technologies? | `docs/engineering-decisions/ENGINEERING_DECISIONS.md` |
| What are the benchmark numbers? | `reports/agent_performance_result.md` |
| Where are the consolidated metrics? | `evaluation/METRICS.md` |
| What broke during the build? | `evaluation/FAILURE_ANALYSIS.md` |
| Where is the dataset snapshot? | `evaluation/data/` |
| What broke during the build? | `LEARNING_LOG.md` |
