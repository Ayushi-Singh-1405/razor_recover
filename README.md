# Repechage

Agentic payment recovery for failed Razorpay checkouts.

Repechage detects at-risk payments, reasons about why they failed, and recovers
the ones worth recovering — while a deterministic policy gate keeps every
action safe, bounded, and fully audited.

**AI reasons. Policy decides. Execution is controlled.**

## Results — 662-event benchmark (simulated)

We ran the full recovery agent and the deterministic benchmark over the same
662 at-risk events under identical §20.7/§20.8 economics — and report the
outcome honestly, including where the agent loses:

| System | Candidates | Recoveries | ₹ Recovered | Bad interventions | Net ₹ |
|---|---:|---:|---:|---:|---:|
| Deterministic benchmark | 662 | 438 | ₹42.9L | 224 | **₹42.4L** |
| AI recovery agent | 408 | 298 | ₹25.8L | 110 | **₹25.5L** |

```
Net ₹ recovered — 662 at-risk events, identical simulation economics:

Deterministic benchmark  ████████████████████████████████████  ₹4,244,118
AI recovery agent        ██████████████████████                ₹2,554,773
```

**The honest read:** the agent is more precise per attempt — 73% targeting
precision vs 66%, with 110 bad interventions vs 224 — but far more
conservative. It attempted recovery on only 408 of 662 events, leaving
~₹16.9L of recoverable revenue untouched. Under the current economics the
**deterministic benchmark is retained for real execution**; the agent's
reasoning is evaluated, not yet execution-authorized.

Every decision, gate override, escalation, and webhook-confirmed recovery is
auditable — that trail, not a perfect number, is the product.

Full breakdown: [agent_performance_result.md](backend/reports/agent_performance_result.md) ·
live charts: `/analytics` · audit trail: `/audit`

## Track 03 — AI Revenue Recovery

**The problem:** failed and abandoned checkouts are recoverable revenue —
but payment gateways only report the failure. Merchants get a failed-payment
notification at best, and the money quietly disappears: no triage, no
recovery attempt, no measurement of what could have been saved.

**The track asks for:** an agent that detects revenue at risk, determines the
appropriate intervention, executes a bounded recovery workflow, measures the
money recovered — with compliant escalation, stopping rules, and a full
audit trail.

**What Revoco delivers against it:**

- Measured money recovered — ₹13,497 of real Test Mode revenue recovered
  through webhook-confirmed payment links, across a 662-event benchmark run
- Compliant escalation — over-cap and low-recoverability cases go to the
  merchant with one-click Approve/Dismiss, fully audited
- Stopping rules — attempt caps, already-recovered checks, and volume caps
  enforced by a deterministic gate the LLM cannot override
- Audit trail — every decision, gate override, and recovery recorded and
  viewable on the Audit page

## Results — 662-event benchmark (simulated)

We ran the full recovery agent and the deterministic benchmark over the same
662 at-risk events under identical §20.7/§20.8 economics — and report the
outcome honestly, including where the agent loses:

| System | Candidates | Recoveries | ₹ Recovered | Bad interventions | Net ₹ |
|---|---:|---:|---:|---:|---:|
| Deterministic benchmark | 662 | 438 | ₹42.9L | 224 | **₹42.4L** |
| AI recovery agent | 408 | 298 | ₹25.8L | 110 | **₹25.5L** |

```
Net ₹ recovered — 662 at-risk events, identical simulation economics:

Deterministic benchmark  ████████████████████████████████████  ₹4,244,118
AI recovery agent        ██████████████████████                ₹2,554,773
```

**The honest read:** the agent is more precise per attempt — 73% targeting
precision vs 66%, with 110 bad interventions vs 224 — but far more
conservative. It attempted recovery on only 408 of 662 events, leaving
~₹16.9L of recoverable revenue untouched. Under the current economics the
**deterministic benchmark is retained for real execution**; the agent's
reasoning is evaluated, not yet execution-authorized.

Every decision, gate override, escalation, and webhook-confirmed recovery is
auditable — that trail, not a perfect number, is the product.

Full breakdown: [reports/agent_performance_result.md](reports/agent_performance_result.md) ·
live charts: `/analytics` · audit trail: `/audit` · metrics: [reports/METRICS.md](reports/METRICS.md) ·
failure record: [reports/FAILURE_ANALYSIS.md](reports/FAILURE_ANALYSIS.md)

## How it works

```
Payment Failure
      ↓
Detect → Diagnose → Decide
      ↓
Policy Gate (deterministic, authoritative)
      ↓
Recover / Escalate to merchant
      ↓
Audit
```

- **Detection** — a deterministic detector flags at-risk payments from observed
  signals only (status, failure reason, recovery-attempt history).
- **Diagnosis & decision** — a recovery agent receives richer permitted context
  (customer history, order-value deviation, checkout behavior) and recommends
  one of five bounded actions.
- **Policy gate** — attempt caps, amount ceilings, action whitelists, and
  confidence floors are enforced by code that cannot be overridden.
- **Evaluation** — the agent is graded in rupees recovered against a
  pre-registered deterministic benchmark on identical events. Ground truth is
  never visible to the agent or the detector.

## Pages

| Route | Description |
|---|---|
| `/` | Public product landing page |
| `/login` | Google sign-in |
| `/dashboard` | Live execution (real Test Mode recovery runs), System Status |
| `/analytics` | Detection benchmark + agent-vs-benchmark evaluation with charts |
| `/audit` | Filterable chronological audit trail |
| `/developers` | API reference, decision schema, policy gates |
| `/security` | Auth model, execution safety, evaluation integrity |
| `/resources` | Policies, evaluation reports, repository |

## API

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | — | Health check |
| GET | `/auth/google/login` | — | Redirect to Google consent |
| GET | `/auth/google/callback` | — | OAuth callback → session cookie |
| GET | `/auth/me` | session | Current merchant (401 otherwise) |
| GET | `/auth/logout` | — | Clears the session |
| POST | `/transactions/create-test-order` | — | Razorpay Test Mode order |
| POST | `/transactions/{id}/create-payment-link` | — | Razorpay payment link |
| POST | `/webhook` | signature | Razorpay webhook (verified, idempotent) |
| GET | `/audit/{transaction_id}` | — | Audit trail for a transaction |
| GET | `/dashboard/summary` | session | Detection + execution + evaluation payload |
| POST | `/dashboard/escalations/{id}/approve` | session | Merchant approves an escalation |
| POST | `/dashboard/escalations/{id}/dismiss` | session | Merchant dismisses an escalation |

## Project structure

```
frontend/            Static pages (vanilla JS ES modules) + theme.css
backend/
  main.py            FastAPI app (pages, auth wiring, summary, webhooks)
  auth.py            Google OAuth + JWT sessions
  dashboard_actions.py  Escalation approve/dismiss
  run_agent.py       Recovery agent runner (policy gates, retries, resume)
  llm_provider.py    OpenRouter structured-decision client
  generate_synthetic_data.py   Seeded benchmark dataset + ground truth
  detect_at_risk.py  Baseline detector (limited observable signals)
  evaluate.py / simulate_outcomes.py / execute_recovery.py
  GROUND_TRUTH_POLICY.md / EXECUTION_POLICY.md
  alembic/           migrations 001-006
  reports/           evaluation reports
tests/               smoke, durability, summary-verification suites
docs/                architecture, specs, workflow plans
```

## Run locally

```bash
python -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env            # add Razorpay, Neon, Google, JWT secrets
cd backend && ../venv/bin/alembic upgrade head
../venv/bin/uvicorn main:app --reload
# open http://localhost:8000/
```

Environment variables: see `.env.example` (Razorpay Test Mode keys, Neon
PostgreSQL URL, Google OAuth client, `JWT_SECRET`, execution-policy caps).

## Documentation

- [GROUND_TRUTH_POLICY.md](backend/GROUND_TRUTH_POLICY.md) — benchmark rules,
  information separation, simulation economics
- [EXECUTION_POLICY.md](backend/EXECUTION_POLICY.md) — what the execution layer
  may do with real money
- [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) — system architecture
- [CHANGELOG.md](CHANGELOG.md) — release history
- [LEARNING_LOG.md](LEARNING_LOG.md) — failures and what they changed

## License

MIT — see [LICENSE](LICENSE)
